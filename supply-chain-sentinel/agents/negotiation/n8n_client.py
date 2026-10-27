"""Action layer = n8n. Every call goes to an n8n Webhook node:  POST {N8N_BASE_URL}/webhook/<workflow>
 - N8N_BASE_URL empty            -> mock mode (demo still works, clearly labelled)
 - n8n unreachable / errors      -> 'fallback' mode (never kills the demo; the agents carry on)
 - N8N_USE_TEST_URL=1            -> uses /webhook-test/ (works only while the n8n editor is 'listening')
Self-test (backend should be running so n8n can call it back):  python -m agents.negotiation.n8n_client
"""
import json, os, uuid, urllib.request
from agents import config  # noqa: F401  (loads .env)


def base_url():
    return os.getenv("N8N_BASE_URL", "").rstrip("/")


def callback_base():
    return os.getenv("BACKEND_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")


def fire(workflow, payload, timeout=10):
    base = base_url()
    if not base:
        return {"execution_id": "mock_" + uuid.uuid4().hex[:8], "mode": "mock", "workflow": workflow, "response": None}
    prefix = "webhook-test" if os.getenv("N8N_USE_TEST_URL") == "1" else "webhook"
    body = {**payload, "callback_base": callback_base()}   # tells the workflow where our backend lives
    try:
        req = urllib.request.Request(f"{base}/{prefix}/{workflow}", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "User-Agent": "SupplyChainSentinel/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
        try:
            resp = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            resp = {}
        if isinstance(resp, list) and resp:
            resp = resp[0]
        resp = resp if isinstance(resp, dict) else {}
        ex = resp.get("executionId") or resp.get("execution_id") or "n8n_" + uuid.uuid4().hex[:8]
        return {"execution_id": str(ex), "mode": "n8n", "workflow": workflow, "response": resp}
    except Exception as e:  # never let the automation layer kill the demo
        return {"execution_id": "fallback_" + uuid.uuid4().hex[:8], "mode": "fallback", "workflow": workflow,
                "response": None, "error": str(e)[:160]}


def status():
    base = base_url()
    if not base:
        return {"configured": False, "reachable": False, "url": None}
    try:
        urllib.request.urlopen(base + "/healthz", timeout=1.5).read()
        return {"configured": True, "reachable": True, "url": base}
    except Exception:
        return {"configured": True, "reachable": False, "url": base}


if __name__ == "__main__":
    print("n8n:", status(), "| callbacks go to:", callback_base())
    sample_terms = {"supplier_id": "S2", "supplier": "Pacific Micro Systems", "quantity": 12300, "unit_price": 112,
                    "lead_time_days": 9, "reliability": 0.9, "baseline_unit_cost": 100, "total_cost": 1377600}
    pings = {
        "send-outreach": {"plan_id": "selftest", "attempt": 1, "draft": "Subject: Self-test\n\nDear Supplier,\n\nThis is a test.", "terms": sample_terms},
        "trigger-budget-review": {"plan_id": "selftest", "attempt": 1, "terms": sample_terms},
        "notify-approved-plan": {"plan_id": "selftest", "supplier": "Pacific Micro Systems", "terms": sample_terms},
    }
    for name, payload in pings.items():
        r = fire(name, payload)
        print(f"\n{name}: mode={r['mode']} execution={r['execution_id']}")
        print("   response:", r["response"] if r["mode"] == "n8n" else r.get("error", "(mock - N8N_BASE_URL not set)"))
