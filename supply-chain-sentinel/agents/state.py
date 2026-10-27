"""Shared plan state. Each agent writes ONLY its own block (see Section 6.1 of the master doc)."""
import uuid
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_plan():
    return {
        "plan_id": "plan_" + uuid.uuid4().hex[:8],
        "status": "monitoring",
        "opened_at": now(),
        "risk_event": None,
        "impact": None,
        "sourcing": None,
        "negotiation": None,
        "budget_review": None,
        "outbox": [],                # emails sent to suppliers (delivered by n8n)
        "negotiation_history": [],   # append-only: one entry per sourcing<->budget round trip
        "human_override": None,
        "trace": [],                 # ordered stage log -> what the dashboard streams
    }


def log(plan, agent, message, data=None):
    entry = {"ts": now(), "agent": agent, "message": message, "data": data or {}}
    plan["trace"].append(entry)
    print(f"[{agent:<11}] {message}")
    return entry
