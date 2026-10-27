"""Orchestrator. Plain-Python state machine for phase 1 -- node names and the conditional edge match
what a LangGraph graph needs, so porting is mechanical."""
from agents import config  # noqa: F401  (loads .env)
import os
from agents.state import new_plan, log
from agents.monitor import monitor_agent
from agents.impact import impact_agent
from agents.sourcing import sourcing_agent
from agents.negotiation import negotiation_agent, n8n_client
from policy_service import budget_agent

MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))


def run_pipeline(kind="port_closure", on_update=None, plan=None):
    """on_update(plan, entry) fires after every stage -- Phase 2 plugs SSE/WebSocket in here."""
    plan = plan or new_plan()

    def emit(agent, msg, data=None):
        e = log(plan, agent, msg, data)
        if on_update:
            on_update(plan, e)

    ev = monitor_agent.run(plan, kind)
    emit("monitor", f"Detected: {ev['headline']} (severity {ev['severity_estimate']}) [{ev['source']}]",
         {"evidence": ev.get("evidence"), "classifier": ev.get("classifier"), "reasoning": ev.get("reasoning")})

    imp = impact_agent.run(plan)
    emit("impact", f"{len(imp['affected_orders'])} orders affected, value at risk {imp['total_value_at_risk']:,.0f}; "
                   f"re-sourcing {imp['resource_quantity']} units of {imp['resource_category']}")

    rejection = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        supplier = sourcing_agent.run(plan, attempt, rejection)
        if supplier is None:
            emit("sourcing", "Shortlist exhausted -> escalating to human")
            break
        emit("sourcing", f"Attempt {attempt}: proposing {supplier['name']} "
                         f"(score {supplier['score']}, {supplier['unit_price']}/unit, {supplier['lead_time_days']}d)")

        neg = negotiation_agent.run(plan, supplier)
        emit("negotiation", f"Outreach drafted by {neg['drafted_by']}, sent via n8n [{neg['n8n_mode']}] exec={neg['n8n_execution_id']}")

        fx = n8n_client.fire("trigger-budget-review", {"plan_id": plan["plan_id"], "attempt": attempt,
                                                      "terms": neg["proposed_terms"]})
        review = budget_agent.from_n8n(plan, attempt, fx) or budget_agent.run(plan, attempt)
        plan["negotiation_history"].append({"attempt": attempt, "supplier": supplier["name"],
                                            "decision": review["decision"], "reason": review["reason"],
                                            "rule": review["policy_rule_applied"], "decided_by": review["decided_by"]})
        emit("budget", f"{review['decision'].upper()} ({review['policy_rule_applied']}) via {review['decided_by']}: {review['reason']}")

        if review["decision"] == "approve":
            plan["status"] = "approved"
            fx = n8n_client.fire("notify-approved-plan", {"plan_id": plan["plan_id"], "supplier": supplier["name"],
                                                         "terms": neg["proposed_terms"], "attempts": attempt,
                                                         "value_at_risk": imp["total_value_at_risk"],
                                                         "orders_protected": len(imp["affected_orders"])})
            emit("orchestrator", f"APPROVED plan with {supplier['name']} after {attempt} attempt(s); "
                                 f"notify workflow [{fx['mode']}] exec={fx['execution_id']}")
            return plan
        rejection = review["reason"]
        plan["status"] = "sourcing"
        emit("orchestrator", f"Loop: rejected -> back to Sourcing with reason attached (attempt {attempt}/{MAX_ATTEMPTS})")

    plan["status"] = "escalated"
    plan["human_override"] = {"required": True, "reason": "attempts exhausted"}
    emit("orchestrator", "ESCALATED to human override")
    return plan
