# Supply Chain Sentinel - Phase 1 (core loop, runs with zero dependencies except PyYAML)

    pip install -r requirements.txt
    python run_demo.py                # port closure scenario
    python run_demo.py factory_fire   # second scenario

Expected: Monitor -> Impact -> Sourcing -> Negotiation -> Budget REJECTS AeroLink (1.42x price)
-> Sourcing resubmits Pacific Micro -> Budget APPROVES -> notify workflow fires.
Set MAX_ATTEMPTS=1 to see the human-escalation path.

Edit policy_service/budget_rules.yaml to change the rules. Set N8N_BASE_URL to use real n8n webhooks.
