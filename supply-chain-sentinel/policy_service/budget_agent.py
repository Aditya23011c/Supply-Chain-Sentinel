"""Budget Agent: evaluates proposed terms against budget_rules.yaml.
Always returns a specific reason + the rule applied (never a bare yes/no).
Callable locally (run) or via n8n (the Trigger-Budget-Review workflow POSTs to /api/policy/review, which calls evaluate)."""
import os, yaml
from agents.state import now

with open(os.path.join(os.path.dirname(__file__), "budget_rules.yaml"), encoding="utf-8") as _f:
    RULES = yaml.safe_load(_f)["rules"]


def check(rule, t):
    rid = rule["id"]
    if rid == "MAX_PRICE_MULTIPLIER":
        mult = t["unit_price"] / t["baseline_unit_cost"]
        return mult <= rule["max_multiplier"], f"unit price is {mult:.2f}x baseline (limit {rule['max_multiplier']}x)"
    if rid == "MAX_LEAD_TIME":
        return t["lead_time_days"] <= rule["max_days"], f"lead time {t['lead_time_days']}d (limit {rule['max_days']}d)"
    if rid == "MIN_RELIABILITY":
        return t["reliability"] >= rule["min_score"], f"reliability {t['reliability']} (min {rule['min_score']})"
    if rid == "MAX_TOTAL_SPEND":
        return t["total_cost"] <= rule["cap"], f"total cost {t['total_cost']:,} (cap {rule['cap']:,})"
    raise ValueError(f"unknown rule {rid}")


def evaluate(terms):
    """Pure function: terms -> (decision, reason, rule_id)."""
    for rule in RULES:
        ok, detail = check(rule, terms)
        if not ok:
            return "reject", f"{rule['description']} -- {detail}", rule["id"]
    return "approve", "All budget rules satisfied", "ALL"


def record(plan, attempt, decision, reason, rule, decided_by):
    plan["budget_review"] = {"event_id": plan["risk_event"]["event_id"], "decision": decision, "reason": reason,
                             "policy_rule_applied": rule, "attempt_number": attempt, "decided_by": decided_by,
                             "processed_at": now()}
    return plan["budget_review"]


def run(plan, attempt):
    d, r, a = evaluate(plan["negotiation"]["proposed_terms"])
    return record(plan, attempt, d, r, a, "policy-service (local)")


def from_n8n(plan, attempt, fx):
    """Use the decision n8n returned - but never trust it blindly: re-check locally, and if they disagree the
    local policy wins. Returns None when n8n gave no usable answer (caller then falls back to run())."""
    resp = fx.get("response") if fx.get("mode") == "n8n" else None
    if not (isinstance(resp, dict) and resp.get("decision") in ("approve", "reject") and resp.get("reason")):
        return None
    d, r, a = evaluate(plan["negotiation"]["proposed_terms"])
    if d != resp["decision"]:
        return record(plan, attempt, d, r, a, "policy-service (n8n answer overridden: mismatch)")
    return record(plan, attempt, d, str(resp["reason"]), str(resp.get("policy_rule_applied", a)), "n8n -> policy-service")
