"""Negotiation Agent. The email is a FIXED template; the terms are computed in code. The LLM (if configured)
may only fill ONE slot: a single plain sentence of business justification - no numbers, no prices - and its
output is validated before use. Anything odd -> safe default sentence. So it can never ramble or invent terms."""
import re
from agents import llm
from agents.state import now
from agents.negotiation import n8n_client

DEFAULT_JUSTIFICATION = "We need to secure replacement supply quickly to protect committed customer deliveries."

TEMPLATE = (
    "Subject: Urgent supply request - {qty} units of {item}\n\n"
    "Dear {supplier},\n\n"
    "{context} {justification}\n\n"
    "We would like to place an order for {qty} units of {item} at {price} per unit, with delivery within {lead} days.\n"
    "Please confirm availability and terms by end of day.\n\nRegards,\nSupply Chain Sentinel (on behalf of procurement)"
)


def justification(plan, supplier):
    if not llm.settings()["configured"]:
        return DEFAULT_JUSTIFICATION, "template"
    ev, imp = plan["risk_event"], plan["impact"]
    try:
        out = llm.chat(
            "You write ONE sentence of business justification inside a supplier outreach email. Output exactly one plain "
            "sentence of at most 28 words. No greeting, no sign-off, no markdown, no numbers, no prices, no quotation marks.",
            f"Disruption: {ev['headline']}. We must re-source {imp['resource_category']} for {len(imp['affected_orders'])} customer orders. "
            f"Supplier: {supplier['name']} ({supplier['location']}). Write the sentence.",
            max_tokens=400, temperature=0.4, timeout=12)
    except llm.LLMError:
        return DEFAULT_JUSTIFICATION, "template (LLM unavailable)"
    s = " ".join(out.replace('"', "").split())
    if not s or len(s) > 240 or re.search(r"\d|http|[$₹€]", s):
        return DEFAULT_JUSTIFICATION, "template (LLM output rejected by validator)"
    if s[-1] not in ".!":
        s += "."
    st = llm.settings()
    return s, f"llm:{st['provider']}/{st['model']}"


def run(plan, supplier):
    imp, ev = plan["impact"], plan["risk_event"]
    qty = imp["resource_quantity"]
    terms = {"supplier_id": supplier["supplier_id"], "supplier": supplier["name"], "quantity": qty,
             "unit_price": supplier["unit_price"], "lead_time_days": supplier["lead_time_days"],
             "reliability": supplier["reliability"], "baseline_unit_cost": imp["baseline_unit_cost"],
             "total_cost": qty * supplier["unit_price"]}
    just, by = justification(plan, supplier)
    context = f"A {ev['disruption_type'].replace('_', ' ')} affecting {ev['location']} has disrupted our primary supply route."
    draft = TEMPLATE.format(qty=qty, item=imp["resource_category"], supplier=supplier["name"], context=context,
                            justification=just, price=supplier["unit_price"], lead=supplier["lead_time_days"])
    attempt = (plan.get("sourcing") or {}).get("attempt_number", 1)
    subject, _, body = draft.partition("\n\n")
    entry = {"attempt": attempt, "supplier": supplier["name"], "subject": subject.replace("Subject: ", "", 1), "body": body,
             "status": "sending", "n8n_execution_id": None}
    plan.setdefault("outbox", []).append(entry)          # visible in the dashboard's supplier inbox
    ex = n8n_client.fire("send-outreach", {"plan_id": plan["plan_id"], "attempt": attempt, "draft": draft, "terms": terms})
    entry["n8n_execution_id"] = ex["execution_id"]
    if entry["status"] != "delivered via n8n":            # the n8n callback may already have marked it delivered
        entry["status"] = {"n8n": "sent via n8n", "mock": "sent (mock - n8n not connected)",
                           "fallback": "n8n unreachable - logged locally"}[ex["mode"]]
    plan["negotiation"] = {"event_id": imp["event_id"], "draft_outreach": draft, "proposed_terms": terms,
                           "drafted_by": by, "n8n_execution_id": ex["execution_id"], "n8n_mode": ex["mode"], "processed_at": now()}
    plan["status"] = "reviewing"
    return plan["negotiation"]
