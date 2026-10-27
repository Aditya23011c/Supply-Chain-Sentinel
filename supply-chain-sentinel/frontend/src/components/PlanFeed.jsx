const DOT = { approved: 'bg-emerald-400', escalated: 'bg-red-400' }

export default function PlanFeed({ plans, selected, onSelect }) {
  return (
    <div className="flex flex-col gap-2">
      {plans.length === 0 && <p className="text-sm text-slate-500">No plans yet. Trigger a disruption.</p>}
      {plans.map((p) => (
        <button key={p.plan_id} onClick={() => onSelect(p.plan_id)}
          className={`rounded-lg border p-3 text-left transition ${selected === p.plan_id ? 'border-sky-400 bg-sky-500/10' : 'glass hover:border-sky-400/50'}`}>
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${DOT[p.status] || 'animate-pulse bg-sky-400'}`} />
            <span className="text-xs font-semibold uppercase text-slate-300">{p.status}</span>
          </div>
          <div className="mt-1 line-clamp-2 text-sm text-slate-200">{p.event || 'Detecting…'}</div>
          <div className="mt-1 font-mono text-[10px] text-slate-500">{p.plan_id}</div>
        </button>
      ))}
    </div>
  )
}
