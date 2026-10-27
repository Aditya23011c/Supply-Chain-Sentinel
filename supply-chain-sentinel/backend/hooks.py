"""What happens when n8n calls the backend back. Plain functions so they can be unit-tested without FastAPI."""
from agents.state import log, now


def outreach_sent(plan, p):
    for m in plan.get("outbox", []):
        if m.get("attempt") == p.get("attempt"):
            m["status"] = "delivered via n8n"
            m["delivered_at"] = now()
            m["n8n_execution_id"] = p.get("execution_id") or m.get("n8n_execution_id")
            if p.get("to"):
                m["to"] = p["to"]
    log(plan, "n8n", f"Outreach delivered to {p.get('supplier', 'supplier')} inbox"
                     f"{' (' + p['to'] + ')' if p.get('to') else ''} - n8n execution {p.get('execution_id')}")


def plan_approved(plan, p):
    if p.get("po_number"):
        plan["purchase_order"] = {k: p.get(k) for k in ("po_number", "supplier", "quantity", "unit_price", "total_cost",
                                                         "expected_delivery", "summary", "execution_id")}
    log(plan, "n8n", f"{p.get('summary') or 'Approval notification sent'} - n8n execution {p.get('execution_id')}")
