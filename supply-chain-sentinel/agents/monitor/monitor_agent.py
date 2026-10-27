"""Monitor Agent.
 - kind 'port_closure' / 'factory_fire': pre-scripted event = the guaranteed demo path.
 - kind 'live_scan': real news + weather, classified by the LLM (or rules). Falls back to the scripted event
   if nothing is found, and says so - the demo never stalls on an empty news day."""
import uuid
from agents.state import now
from agents.monitor import feeds

SCRIPTED_EVENTS = {
    "port_closure": {"disruption_type": "port_closure", "location": "Mumbai",
                     "headline": "Port of Nhava Sheva (JNPT) closed for 5 days after severe cyclone warning",
                     "source": "scripted-demo-trigger", "severity_estimate": 0.85},
    "factory_fire": {"disruption_type": "supplier_factory_fire", "location": "Chennai",
                     "headline": "Fire halts operations at a key electronics supplier near Chennai",
                     "source": "scripted-demo-trigger", "severity_estimate": 0.7},
}
LIVE_KIND = "live_scan"
KINDS = list(SCRIPTED_EVENTS) + [LIVE_KIND]


def trigger_scripted(kind="port_closure"):
    ev = dict(SCRIPTED_EVENTS[kind])
    ev["event_id"] = "evt_" + uuid.uuid4().hex[:6]
    ev["detected_at"] = now()
    ev["classifier"] = "scripted"
    return ev


def scan_live():
    return feeds.scan_live()


def run(plan, kind="port_closure"):
    if kind == LIVE_KIND:
        event = scan_live()
        if event is None:
            event = trigger_scripted("port_closure")
            event["source"] = "scripted-fallback (live scan found no disruption)"
    else:
        event = trigger_scripted(kind)
    plan["risk_event"] = event
    plan["status"] = "assessing"
    return event
