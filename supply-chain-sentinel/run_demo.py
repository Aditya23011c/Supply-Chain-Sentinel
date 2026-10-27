import json, sys
from agents.orchestrator.graph import run_pipeline

kind = sys.argv[1] if len(sys.argv) > 1 else "port_closure"
plan = run_pipeline(kind)
path = f"runs/{plan['plan_id']}.json"
json.dump(plan, open(path, "w"), indent=2)
print(f"\nStatus: {plan['status']}  |  full plan saved to {path}")
