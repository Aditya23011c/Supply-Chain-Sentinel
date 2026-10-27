"""Run:  python -m unittest tests.test_phase4 -v
No internet / n8n needed: a fake n8n server stands in, and each workflow's real JavaScript is executed with Node."""
import contextlib, io, json, os, shutil, subprocess, threading, unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from agents import config  # noqa: F401  (loads .env first, then we neutralise it)
for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "LLM_PROVIDER", "N8N_BASE_URL"):
    os.environ.pop(k, None)

from agents.negotiation import n8n_client
from agents.orchestrator.graph import run_pipeline
from policy_service import budget_agent
from backend import hooks

WF_DIR = os.path.join(os.path.dirname(__file__), "..", "n8n-workflows")
NAMES = ["send-outreach", "trigger-budget-review", "notify-approved-plan"]
TERMS = {"supplier_id": "S2", "supplier": "Pacific Micro Systems", "quantity": 12300, "unit_price": 112, "lead_time_days": 9,
         "reliability": 0.9, "baseline_unit_cost": 100, "total_cost": 1377600}


def load(name):
    with open(os.path.join(WF_DIR, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


HARNESS = r"""
const fs = require('fs');
const { workflow: wf, body, policy } = JSON.parse(fs.readFileSync(0, 'utf8'));
const byName = Object.fromEntries(wf.nodes.map(n => [n.name, n]));
const order = ['Webhook'];
while (wf.connections[order[order.length - 1]]) order.push(wf.connections[order[order.length - 1]].main[0][0].node);
const out = {}, requests = [], execution = { id: '777' };
const $ = (name) => ({ first: () => ({ json: out[name] }), all: () => [{ json: out[name] }] });
const evalExpr = (expr, json) => { const m = /^=\{\{([\s\S]*)\}\}$/.exec(expr); return new Function('$', '$json', '$execution', 'return (' + (m ? m[1] : expr) + ')')($, json, execution); };
let prev = null;
for (const name of order) {
  const n = byName[name]; let json;
  if (n.type.endsWith('.webhook')) json = { headers: {}, params: {}, query: {}, body };
  else if (n.type.endsWith('.code')) json = new Function('$input', '$', '$execution', n.parameters.jsCode)({ first: () => ({ json: prev }) }, $, execution)[0].json;
  else if (n.type.endsWith('.httpRequest')) { requests.push({ url: evalExpr(n.parameters.url, prev), body: JSON.parse(evalExpr(n.parameters.jsonBody, prev)) }); json = policy; }
  else if (n.type.endsWith('.respondToWebhook')) json = prev;
  out[name] = json; prev = json;
}
console.log(JSON.stringify({ final: prev, requests, order }));
"""


def run_workflow(name, body, policy=None):
    r = subprocess.run(["node", "-e", HARNESS], input=json.dumps({"workflow": load(name), "body": body, "policy": policy or {"ok": True}}),
                       capture_output=True, text=True, timeout=20)
    if r.returncode != 0:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


class WorkflowFiles(unittest.TestCase):
    def test_structure(self):
        for name in NAMES:
            wf = load(name)
            nodes = {n["name"]: n for n in wf["nodes"]}
            hook = nodes["Webhook"]
            self.assertEqual(hook["parameters"]["path"], name)                      # URL must match what the client calls
            self.assertEqual(hook["parameters"]["responseMode"], "responseNode")
            for src, c in wf["connections"].items():
                self.assertIn(src, nodes)
                for tgt in c["main"][0]:
                    self.assertIn(tgt["node"], nodes)
            self.assertEqual(len({n["id"] for n in wf["nodes"]}), len(wf["nodes"]))   # unique ids
            http_nodes = [n for n in wf["nodes"] if n["type"].endswith("httpRequest")]
            self.assertTrue(http_nodes and all(n.get("onError") == "continueRegularOutput" for n in http_nodes))
            self.assertFalse(wf["active"])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_send_outreach_logic(self):
        body = {"plan_id": "plan_ab12cd34", "attempt": 2, "terms": TERMS, "callback_base": "http://127.0.0.1:8000",
                "draft": "Subject: Urgent supply request - 12300 units of electronic-components\n\nDear Pacific Micro Systems,\n\nPlease confirm."}
        res = run_workflow("send-outreach", body)
        req = res["requests"][0]
        self.assertEqual(req["url"], "http://127.0.0.1:8000/webhooks/n8n/outreach-sent")
        self.assertEqual((req["body"]["plan_id"], req["body"]["attempt"], req["body"]["execution_id"]), ("plan_ab12cd34", 2, "777"))
        self.assertTrue(req["body"]["subject"].startswith("Urgent supply request"))
        self.assertEqual(req["body"]["to"], "sales@pacificmicrosystems.example")
        self.assertEqual(res["final"]["executionId"], "777")
        self.assertTrue(res["final"]["ok"])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_budget_review_logic(self):
        body = {"plan_id": "plan_ab12cd34", "attempt": 2, "terms": TERMS, "callback_base": "http://127.0.0.1:8000"}
        res = run_workflow("trigger-budget-review", body, {"decision": "reject", "reason": "too pricey", "policy_rule_applied": "MAX_PRICE_MULTIPLIER"})
        self.assertEqual(res["requests"][0]["url"], "http://127.0.0.1:8000/api/policy/review")
        self.assertEqual(res["requests"][0]["body"], {"terms": TERMS})
        f = res["final"]
        self.assertEqual((f["ok"], f["decision"], f["policy_rule_applied"], f["priority"]), (True, "reject", "MAX_PRICE_MULTIPLIER", "MEDIUM"))
        self.assertEqual(f["ticket"], "REV-12CD34-2")
        down = run_workflow("trigger-budget-review", body, {"error": "ECONNREFUSED"})["final"]     # policy service down
        self.assertFalse(down["ok"])
        self.assertNotIn("decision", down)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_purchase_order_logic(self):
        body = {"plan_id": "plan_ab12cd34", "supplier": "Pacific Micro Systems", "terms": TERMS, "callback_base": "http://127.0.0.1:8000"}
        res = run_workflow("notify-approved-plan", body)
        sent = res["requests"][0]
        self.assertEqual(sent["url"], "http://127.0.0.1:8000/webhooks/n8n/plan-approved")
        self.assertTrue(sent["body"]["po_number"].startswith("PO-"))
        self.assertEqual(sent["body"]["execution_id"], "777")
        self.assertIn("Pacific Micro Systems", sent["body"]["summary"])
        eta = (datetime.now(timezone.utc) + timedelta(days=9)).date().isoformat()
        self.assertIn(sent["body"]["expected_delivery"], {eta, (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat()})


class FakeN8n:
    """Pretends to be n8n: answers webhooks like our real workflows do."""
    def __init__(self, mode="ok"):
        self.requests, outer = [], self
        self.mode = mode

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(data)

            def do_GET(self):
                self._send(200, {"status": "ok"}) if self.path == "/healthz" else self._send(404, {})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                name = self.path.rsplit("/", 1)[-1]
                outer.requests.append((name, self.path, body))
                if outer.mode == "down":
                    return self._send(500, {"message": "boom"})
                resp = {"ok": True, "executionId": f"fake-{len(outer.requests)}"}
                if name == "trigger-budget-review":
                    d, r, a = ("approve", "n8n says fine", "ALL") if outer.mode == "liar" else budget_agent.evaluate(body["terms"])
                    resp.update(decision=d, reason=r, policy_rule_applied=a)
                self._send(200, resp)

        self.server = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown(); self.server.server_close()

    def names(self):
        return [n for n, _, _ in self.requests]


def quiet_pipeline(kind="port_closure"):
    with contextlib.redirect_stdout(io.StringIO()):
        return run_pipeline(kind)


class Client(unittest.TestCase):
    def setUp(self):
        self.fake = FakeN8n()
        self.addCleanup(self.fake.stop)
        p = mock.patch.dict(os.environ, {"N8N_BASE_URL": self.fake.url, "BACKEND_PUBLIC_URL": "http://127.0.0.1:8000"})
        p.start(); self.addCleanup(p.stop)

    def test_fire_roundtrip(self):
        r = n8n_client.fire("send-outreach", {"plan_id": "p1", "attempt": 1})
        self.assertEqual((r["mode"], r["execution_id"]), ("n8n", "fake-1"))
        name, path, body = self.fake.requests[0]
        self.assertEqual(path, "/webhook/send-outreach")
        self.assertEqual(body["callback_base"], "http://127.0.0.1:8000")

    def test_status(self):
        self.assertEqual(n8n_client.status()["reachable"], True)
        with mock.patch.dict(os.environ, {"N8N_BASE_URL": "http://127.0.0.1:9"}):
            self.assertEqual(n8n_client.status(), {"configured": True, "reachable": False, "url": "http://127.0.0.1:9"})
        with mock.patch.dict(os.environ, {"N8N_BASE_URL": ""}):
            self.assertFalse(n8n_client.status()["configured"])

    def test_full_pipeline_through_n8n(self):
        plan = quiet_pipeline()
        self.assertEqual(plan["status"], "approved")
        self.assertEqual([h["decision"] for h in plan["negotiation_history"]], ["reject", "approve"])
        self.assertTrue(all("n8n -> policy-service" == h["decided_by"] for h in plan["negotiation_history"]))
        self.assertEqual(sorted(self.fake.names()), sorted(["send-outreach"] * 2 + ["trigger-budget-review"] * 2 + ["notify-approved-plan"]))
        notify = [b for n, _, b in self.fake.requests if n == "notify-approved-plan"][0]
        self.assertEqual((notify["plan_id"], notify["attempts"], notify["orders_protected"]), (plan["plan_id"], 2, 16))
        self.assertEqual(notify["terms"]["supplier"], "Pacific Micro Systems")
        self.assertEqual(len(plan["outbox"]), 2)

    def test_n8n_cannot_override_policy(self):
        self.fake.mode = "liar"                      # n8n claims AeroLink (1.42x) is fine
        plan = quiet_pipeline()
        first = plan["negotiation_history"][0]
        self.assertEqual(first["decision"], "reject")
        self.assertIn("overridden", first["decided_by"])


class Fallbacks(unittest.TestCase):
    def test_n8n_down_demo_survives(self):
        fake = FakeN8n("down"); self.addCleanup(fake.stop)
        with mock.patch.dict(os.environ, {"N8N_BASE_URL": fake.url}):
            plan = quiet_pipeline()
        self.assertEqual(plan["status"], "approved")
        self.assertEqual(plan["negotiation"]["n8n_mode"], "fallback")
        self.assertEqual(plan["negotiation_history"][1]["decided_by"], "policy-service (local)")
        self.assertTrue(all("unreachable" in m["status"] for m in plan["outbox"]))

    def test_mock_mode(self):
        with mock.patch.dict(os.environ, {"N8N_BASE_URL": ""}):
            plan = quiet_pipeline("factory_fire")
        self.assertEqual(plan["status"], "approved")
        self.assertTrue(all("mock" in m["status"] for m in plan["outbox"]))


class Hooks(unittest.TestCase):
    def test_outreach_sent_marks_delivered(self):
        plan = {"trace": [], "outbox": [{"attempt": 1, "status": "sending"}, {"attempt": 2, "status": "sending"}]}
        hooks.outreach_sent(plan, {"attempt": 2, "supplier": "Acme", "to": "sales@acme.example", "execution_id": "42"})
        self.assertEqual(plan["outbox"][0]["status"], "sending")
        self.assertEqual((plan["outbox"][1]["status"], plan["outbox"][1]["to"]), ("delivered via n8n", "sales@acme.example"))
        self.assertEqual(plan["trace"][-1]["agent"], "n8n")

    def test_plan_approved_stores_purchase_order(self):
        plan = {"trace": []}
        hooks.plan_approved(plan, {"po_number": "PO-1", "supplier": "Acme", "summary": "PO-1 ok", "execution_id": "9", "expected_delivery": "2026-10-20"})
        self.assertEqual(plan["purchase_order"]["po_number"], "PO-1")
        hooks.plan_approved(plan := {"trace": []}, {"summary": "no po"})   # callback without a PO must not crash
        self.assertNotIn("purchase_order", plan)


if __name__ == "__main__":
    unittest.main()
