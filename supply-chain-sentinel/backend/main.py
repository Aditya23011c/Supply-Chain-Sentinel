"""Phase 2 backend. Run from the project root:   uvicorn backend.main:app --reload --port 8000
Then open http://localhost:8000  (live test page)  or  http://localhost:8000/docs  (Swagger)."""
import asyncio, json, os, threading, time
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from agents import config, llm  # noqa: F401  (loads .env)
from agents.monitor import monitor_agent
from agents.state import new_plan, log, now
from agents.orchestrator.graph import run_pipeline
from agents.negotiation import n8n_client
from policy_service import budget_agent
from fastapi import Depends
from backend.auth import router as auth_router, require_user
from backend import hooks

PACE = float(os.getenv("PACE_SECONDS", "1.5"))   # delay between stages so judges can watch (0 = instant)
RUNS_DIR = os.path.join(os.path.dirname(__file__), "..", "runs")
PLANS: dict = {}                                  # in-memory store: plan_id -> plan
DONE = ("approved", "escalated")

app = FastAPI(title="Supply Chain Sentinel API")
app.include_router(auth_router)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------- models ----------
class TriggerBody(BaseModel):
    kind: str = "port_closure"        # port_closure | factory_fire | live_scan


class OverrideBody(BaseModel):
    action: str = "approve"           # approve | reject
    supplier_id: Optional[str] = None
    note: str = ""


# ---------- helpers ----------
def _persist(plan):
    os.makedirs(RUNS_DIR, exist_ok=True)
    with open(os.path.join(RUNS_DIR, f"{plan['plan_id']}.json"), "w") as f:
        json.dump(plan, f, indent=2)


def _run_in_background(plan, kind):
    def pace(_plan, _entry):
        time.sleep(PACE)
    try:
        run_pipeline(kind, on_update=pace, plan=plan)
    except Exception as e:                       # never leave a plan hanging on stage
        plan["status"] = "escalated"
        plan["human_override"] = {"required": True, "reason": f"pipeline error: {e}"}
        log(plan, "orchestrator", f"ERROR -> escalated: {e}")
    plan["finished"] = True
    _persist(plan)


# ---------- routes ----------
@app.get("/health")
def health():
    return {"ok": True, "plans": len(PLANS)}


@app.get("/api/system/status", dependencies=[Depends(require_user)])
def system_status():
    return {"llm": llm.settings(), "kinds": monitor_agent.KINDS, "n8n": n8n_client.status()}


@app.post("/api/events/trigger", dependencies=[Depends(require_user)])
def trigger(body: TriggerBody = TriggerBody()):
    if body.kind not in monitor_agent.KINDS:
        raise HTTPException(400, f"unknown kind '{body.kind}', use one of {monitor_agent.KINDS}")
    plan = new_plan()
    PLANS[plan["plan_id"]] = plan
    threading.Thread(target=_run_in_background, args=(plan, body.kind), daemon=True).start()
    return {"plan_id": plan["plan_id"], "stream": f"/api/plans/{plan['plan_id']}/stream"}


@app.get("/api/plans", dependencies=[Depends(require_user)])
def list_plans(status: Optional[str] = None):
    items = [{"plan_id": p["plan_id"], "status": p["status"], "opened_at": p["opened_at"],
              "event": (p["risk_event"] or {}).get("headline")} for p in PLANS.values()]
    if status:
        items = [i for i in items if i["status"] == status]
    return sorted(items, key=lambda i: i["opened_at"], reverse=True)


@app.get("/api/plans/{plan_id}", dependencies=[Depends(require_user)])
def get_plan(plan_id: str):
    if plan_id not in PLANS:
        raise HTTPException(404, "plan not found")
    return PLANS[plan_id]


@app.get("/api/plans/{plan_id}/stream", dependencies=[Depends(require_user)])
async def stream(plan_id: str):
    """Server-Sent Events. Replays everything so far, then pushes each new stage as it happens."""
    if plan_id not in PLANS:
        raise HTTPException(404, "plan not found")
    plan = PLANS[plan_id]

    async def gen():
        sent = 0
        while True:
            trace = plan["trace"]
            while sent < len(trace):
                payload = {"entry": trace[sent], "status": plan["status"],
                           "negotiation_history": plan["negotiation_history"],
                           "shortlist": (plan["sourcing"] or {}).get("shortlist"),
                           "outbox": plan.get("outbox", [])}
                yield f"event: stage\ndata: {json.dumps(payload)}\n\n"
                sent += 1
            if plan.get("finished") and sent >= len(plan["trace"]):
                yield f"event: done\ndata: {json.dumps(plan)}\n\n"
                return
            await asyncio.sleep(0.25)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/plans/{plan_id}/override", dependencies=[Depends(require_user)])
def override(plan_id: str, body: OverrideBody):
    if plan_id not in PLANS:
        raise HTTPException(404, "plan not found")
    plan = PLANS[plan_id]
    if plan["status"] != "escalated":
        raise HTTPException(409, f"override only allowed on escalated plans (status={plan['status']})")
    shortlist = (plan["sourcing"] or {}).get("shortlist") or []
    chosen = next((s for s in shortlist if s["supplier_id"] == body.supplier_id), None) if body.supplier_id else None
    if body.action == "approve" and not chosen:
        raise HTTPException(400, "supplier_id from the shortlist is required to approve")
    plan["human_override"] = {"required": False, "action": body.action, "supplier_id": body.supplier_id,
                              "note": body.note, "at": now()}
    if body.action == "approve":
        plan["status"] = "approved"
        imp = plan["impact"] or {}
        qty = imp.get("resource_quantity", 0)
        terms = {"supplier_id": chosen["supplier_id"], "supplier": chosen["name"], "quantity": qty, "unit_price": chosen["unit_price"],
                 "lead_time_days": chosen["lead_time_days"], "reliability": chosen["reliability"],
                 "baseline_unit_cost": imp.get("baseline_unit_cost"), "total_cost": qty * chosen["unit_price"]}
        fx = n8n_client.fire("notify-approved-plan", {"plan_id": plan_id, "supplier": chosen["name"], "terms": terms, "override": True})
        log(plan, "human", f"OVERRIDE approved {chosen['name']} (notify exec={fx['execution_id']})")
    else:
        log(plan, "human", f"OVERRIDE rejected plan: {body.note}")
    _persist(plan)
    return plan


@app.post("/api/policy/review")
def policy_review(payload: dict):
    """Budget Agent as a service. The n8n 'Trigger-Budget-Review' workflow calls this. Pure function, no plan data."""
    terms = payload.get("terms") or {}
    try:
        decision, reason, rule = budget_agent.evaluate(terms)
    except (KeyError, TypeError, ZeroDivisionError) as e:
        raise HTTPException(400, f"invalid terms: {e}")
    return {"decision": decision, "reason": reason, "policy_rule_applied": rule}


@app.post("/webhooks/n8n/outreach-sent")
def n8n_outreach_sent(payload: dict):
    plan = PLANS.get(payload.get("plan_id", ""))
    if plan:
        hooks.outreach_sent(plan, payload)
    return {"received": True}


@app.post("/webhooks/n8n/plan-approved")
def n8n_plan_approved(payload: dict):
    plan = PLANS.get(payload.get("plan_id", ""))
    if plan:
        hooks.plan_approved(plan, payload)
    return {"received": True}


# ---------- landing info (the real UI is the React dashboard) ----------
@app.get("/", response_class=HTMLResponse)
def home():
    return """<body style="font-family:system-ui;background:#0f172a;color:#e2e8f0;padding:40px">
<h2>Supply Chain Sentinel API is running</h2>
<p>Open the dashboard: <a style="color:#38bdf8" href="http://localhost:5173">http://localhost:5173</a></p>
<p>API docs: <a style="color:#38bdf8" href="/docs">/docs</a></p></body>"""
