const money = (n) => '₹' + Number(n).toLocaleString('en-IN')

export default function FinalPlanView({ plan, attempts }) {
  if (!plan) return null
  const t = plan.negotiation?.proposed_terms
  const b = plan.budget_review
  const imp = plan.impact
  if (plan.status !== 'approved' || !t) return null
  return (
    <div className="anim-slide-in rounded-2xl border border-emerald-500/60 bg-emerald-500/10 p-5">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-2xl">✅</span>
        <h3 className="text-lg font-bold text-emerald-300">Backup plan approved — no human in the loop</h3>
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
        <Stat label="Supplier" value={t.supplier} />
        <Stat label="Order" value={`${Number(t.quantity).toLocaleString('en-IN')} units @ ₹${t.unit_price}`} />
        <Stat label="Total cost" value={money(t.total_cost)} />
        <Stat label="Lead time" value={`${t.lead_time_days} days`} />
        <Stat label="Value at risk covered" value={imp ? money(imp.total_value_at_risk) : '-'} />
        <Stat label="Orders protected" value={imp ? imp.affected_orders.length : '-'} />
        <Stat label="Approved on attempt" value={`${b?.attempt_number ?? attempts}`} />
        <Stat label="n8n execution" value={plan.negotiation?.n8n_execution_id} />
        {plan.purchase_order?.po_number && <Stat label="Purchase order" value={plan.purchase_order.po_number} />}
        {plan.purchase_order?.expected_delivery && <Stat label="Delivery by" value={plan.purchase_order.expected_delivery} />}
      </div>
      <p className="mt-3 text-xs text-slate-400">Budget Agent: {b?.reason}</p>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div className="rounded-lg bg-slate-900/70 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="font-semibold text-slate-100">{value}</div>
    </div>
  )
}
