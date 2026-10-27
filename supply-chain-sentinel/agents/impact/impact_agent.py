"""Impact Agent: event -> affected orders, ranked by severity/urgency."""
import json, os
from datetime import date
from agents.state import now

DB = os.path.join(os.path.dirname(__file__), "..", "..", "data", "orders_inventory.json")
TODAY = date(2026, 10, 10)  # fixed so the demo is deterministic
TIER_W = {"A": 1.0, "B": 0.6, "C": 0.3}


def severity(order):
    days_left = max((date.fromisoformat(order["due_date"]) - TODAY).days, 0)
    urgency = max(0.0, 1 - days_left / 25)
    value = min(order["order_value"] / 300000, 1.0)
    penalty = order["sla_penalty_pct"] / 8
    return round(0.35 * urgency + 0.25 * value + 0.2 * TIER_W[order["customer_tier"]] + 0.2 * penalty, 3)


def run(plan):
    ev = plan["risk_event"]
    with open(DB, encoding="utf-8") as f:
        orders = json.load(f)
    affected = [o for o in orders if o["route_node"] == ev["location"]]
    for o in affected:
        o["severity_score"] = severity(o)
    ranked = sorted(affected, key=lambda o: o["severity_score"], reverse=True)
    by_cat = {}
    for o in ranked:
        by_cat[o["category"]] = by_cat.get(o["category"], 0) + o["order_value"]
    top_cat = max(by_cat, key=by_cat.get)
    cat_orders = [o for o in ranked if o["category"] == top_cat]
    plan["impact"] = {
        "event_id": ev["event_id"],
        "affected_orders": [o["order_id"] for o in ranked],
        "ranked_impact_report": ranked[:5],
        "total_value_at_risk": round(sum(o["order_value"] for o in ranked), 2),
        "resource_category": top_cat,
        "resource_quantity": sum(o["quantity"] for o in cat_orders),
        "baseline_unit_cost": cat_orders[0]["baseline_unit_cost"],
        "processed_at": now(),
    }
    plan["status"] = "sourcing"
    return plan["impact"]
