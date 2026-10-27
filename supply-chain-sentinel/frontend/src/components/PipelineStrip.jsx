const STAGES = [
  { id: 'monitor', label: 'Monitor', icon: '📡' },
  { id: 'impact', label: 'Impact', icon: '📊' },
  { id: 'sourcing', label: 'Sourcing', icon: '🔎' },
  { id: 'negotiation', label: 'Negotiation', icon: '✉️' },
  { id: 'budget', label: 'Budget', icon: '⚖️' },
]

export default function PipelineStrip({ entries, status }) {
  const seen = new Set(entries.map((e) => e.agent))
  const last = [...entries].reverse().find((e) => STAGES.some((s) => s.id === e.agent))
  const lastRaw = entries[entries.length - 1]
  // after a loop-back the plan is "in" sourcing again
  const active = lastRaw?.agent === 'orchestrator' && status === 'sourcing' ? 'sourcing' : last?.agent
  const finished = status === 'approved' || status === 'escalated'

  return (
    <div className="flex flex-wrap items-center gap-2">
      {STAGES.map((s, i) => {
        const done = seen.has(s.id) && (finished || s.id !== active)
        const isActive = !finished && s.id === active
        return (
          <div key={s.id} className="flex items-center gap-2">
            <div className={`flex flex-col items-center rounded-xl border px-4 py-3 transition-all duration-500 ${
              isActive ? 'anim-active border-sky-400 bg-sky-500/10' : done ? 'border-emerald-500/60 bg-emerald-500/10' : 'border-slate-600/60 bg-slate-900/40'}`}>
              <span className="text-xl">{s.icon}</span>
              <span className="text-xs font-medium text-slate-200">{s.label}</span>
            </div>
            {i < STAGES.length - 1 && <span className="text-slate-600">→</span>}
          </div>
        )
      })}
    </div>
  )
}
