// Scripted run that mirrors exactly what the backend streams. Used by "Run demo (no backend)".
const S = (id, name, loc, price, lead, rel, score) => ({
  supplier_id: id, name, location: loc, unit_price: price, lead_time_days: lead, reliability: rel, score, status: 'pending',
})
const base = () => [
  S('S1', 'AeroLink Components', 'Singapore', 142, 4, 0.95, 0.851),
  S('S2', 'Pacific Micro Systems', 'Colombo', 112, 9, 0.9, 0.838),
  S('S3', 'Delta Circuits FZE', 'Dubai', 108, 16, 0.85, 0.758),
  S('S4', 'Orion Electronics', 'Ho Chi Minh City', 98, 21, 0.7, 0.67),
]
const withStatus = (m) => base().map((s) => ({ ...s, status: m[s.supplier_id] || 'pending' }))

export function buildDemoSequence() {
  const e = (agent, message) => ({ agent, message, ts: new Date().toISOString() })
  const rej = { attempt: 1, supplier: 'AeroLink Components', decision: 'reject', rule: 'MAX_PRICE_MULTIPLIER',
    reason: 'Unit price must not exceed 1.15x the original supplier cost -- unit price is 1.42x baseline (limit 1.15x)' }
  const app = { attempt: 2, supplier: 'Pacific Micro Systems', decision: 'approve', rule: 'ALL', reason: 'All budget rules satisfied' }

  const steps = [
    { entry: e('monitor', 'Detected: Port of Nhava Sheva (JNPT) closed for 5 days after severe cyclone warning (severity 0.85)'), status: 'assessing', negotiation_history: [], shortlist: null },
    { entry: e('impact', '16 orders affected, value at risk 1,862,000; re-sourcing 12300 units of electronic-components'), status: 'sourcing', negotiation_history: [], shortlist: null },
    { entry: e('sourcing', 'Attempt 1: proposing AeroLink Components (score 0.851, 142/unit, 4d)'), status: 'negotiating', negotiation_history: [], shortlist: withStatus({ S1: 'proposed' }) },
    { entry: e('negotiation', 'Outreach sent via n8n [mock] exec=mock_demo_01'), status: 'reviewing', negotiation_history: [], shortlist: withStatus({ S1: 'proposed' }) },
    { entry: e('budget', 'REJECT (MAX_PRICE_MULTIPLIER): ' + rej.reason), status: 'reviewing', negotiation_history: [rej], shortlist: withStatus({ S1: 'proposed' }) },
    { entry: e('orchestrator', 'Loop: rejected -> back to Sourcing with reason attached (attempt 1/3)'), status: 'sourcing', negotiation_history: [rej], shortlist: withStatus({ S1: 'proposed' }) },
    { entry: e('sourcing', 'Attempt 2: proposing Pacific Micro Systems (score 0.838, 112/unit, 9d)'), status: 'negotiating', negotiation_history: [rej], shortlist: withStatus({ S1: 'rejected', S2: 'proposed' }) },
    { entry: e('negotiation', 'Outreach sent via n8n [mock] exec=mock_demo_02'), status: 'reviewing', negotiation_history: [rej], shortlist: withStatus({ S1: 'rejected', S2: 'proposed' }) },
    { entry: e('budget', 'APPROVE (ALL): All budget rules satisfied'), status: 'reviewing', negotiation_history: [rej, app], shortlist: withStatus({ S1: 'rejected', S2: 'proposed' }) },
    { entry: e('orchestrator', 'APPROVED plan with Pacific Micro Systems after 2 attempt(s); notify workflow exec=mock_demo_03'), status: 'approved', negotiation_history: [rej, app], shortlist: withStatus({ S1: 'rejected', S2: 'proposed' }) },
  ]
  const body = (sup, price, lead) => `Dear ${sup},\n\nA port closure affecting Mumbai has disrupted our primary supply route. We need to secure replacement supply quickly to protect committed customer deliveries.\n\nWe would like to place an order for 12300 units of electronic-components at ${price} per unit, with delivery within ${lead} days.\nPlease confirm availability and terms by end of day.\n\nRegards,\nSupply Chain Sentinel (on behalf of procurement)`
  const m1 = { attempt: 1, supplier: 'AeroLink Components', subject: 'Urgent supply request - 12300 units of electronic-components', to: 'sales@aerolinkcomponents.example', body: body('AeroLink Components', 142, 4), status: 'delivered via n8n', n8n_execution_id: 'mock_demo_01' }
  const m2 = { attempt: 2, supplier: 'Pacific Micro Systems', subject: 'Urgent supply request - 12300 units of electronic-components', to: 'sales@pacificmicrosystems.example', body: body('Pacific Micro Systems', 112, 9), status: 'delivered via n8n', n8n_execution_id: 'mock_demo_02' }
  steps.forEach((s, i) => { s.outbox = i >= 7 ? [m1, m2] : i >= 3 ? [m1] : [] })
  const final = {
    plan_id: 'demo_plan', status: 'approved',
    impact: { total_value_at_risk: 1862000, affected_orders: new Array(16).fill(0), resource_quantity: 12300, resource_category: 'electronic-components' },
    negotiation: { n8n_execution_id: 'mock_demo_02', proposed_terms: { supplier: 'Pacific Micro Systems', quantity: 12300, unit_price: 112, lead_time_days: 9, total_cost: 1377600 } },
    outbox: [m1, m2],
    purchase_order: { po_number: 'PO-DEMO-0001', expected_delivery: '2026-10-19' },
    budget_review: { decision: 'approve', reason: 'All budget rules satisfied', policy_rule_applied: 'ALL', attempt_number: 2 },
  }
  return { steps, final }
}
