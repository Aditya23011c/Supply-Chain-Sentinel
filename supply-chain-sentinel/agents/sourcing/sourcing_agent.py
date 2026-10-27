"""Sourcing Agent: score alternates; on retry pick the NEXT-best, never the rejected one."""
import json, os
from agents.state import now

DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "supplier_directory.json")
W_REL, W_SPEED, W_PRICE = 0.4, 0.3, 0.3


def score(s, baseline):
    speed = max(0.0, 1 - s["lead_time_days"] / 30)
    price = min(1.0, baseline / s["unit_price"])
    return round(W_REL * s["reliability"] + W_SPEED * speed + W_PRICE * price, 3)


def run(plan, attempt, rejection_reason=None):
    imp = plan["impact"]
    if attempt == 1:
        with open(DIR, encoding="utf-8") as f:
            cands = [s for s in json.load(f) if s["category"] == imp["resource_category"]]
        shortlist = []
        for s in cands:
            s = dict(s)
            s["score"] = score(s, imp["baseline_unit_cost"])
            s["status"] = "pending"
            shortlist.append(s)
        shortlist.sort(key=lambda s: s["score"], reverse=True)
    else:
        shortlist = plan["sourcing"]["shortlist"]
        for s in shortlist:
            if s["status"] == "proposed":
                s["status"] = "rejected"
    nxt = next((s for s in shortlist if s["status"] == "pending"), None)
    if nxt:
        nxt["status"] = "proposed"
    plan["sourcing"] = {
        "event_id": imp["event_id"], "shortlist": shortlist,
        "attempt_number": attempt, "rejection_reason_received": rejection_reason,
        "processed_at": now(),
    }
    plan["status"] = "negotiating"
    return nxt
