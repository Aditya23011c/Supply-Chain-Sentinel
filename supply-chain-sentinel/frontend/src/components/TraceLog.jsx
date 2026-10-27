import { useEffect, useRef } from 'react'

const COLOR = {
  monitor: 'text-amber-300', impact: 'text-violet-300', sourcing: 'text-sky-300', negotiation: 'text-pink-300',
  budget: 'text-emerald-300', orchestrator: 'text-orange-300', human: 'text-yellow-200', n8n: 'text-cyan-300',
}

export default function TraceLog({ entries }) {
  const end = useRef(null)
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [entries.length])
  return (
    <div className="h-56 overflow-y-auto rounded-lg bg-black/40 p-3 font-mono text-xs">
      {entries.length === 0 && <span className="text-slate-600">No activity yet.</span>}
      {entries.map((e, i) => (
        <div key={i} className="anim-slide-in mb-1">
          <span className={`font-bold ${COLOR[e.agent] || 'text-slate-300'}`}>[{e.agent}]</span>{' '}
          <span className="text-slate-300">{e.message}</span>
          {e.data?.evidence?.length > 0 && (
            <div className="ml-4 mt-0.5 text-[11px] text-slate-400">
              {e.data.classifier && <div>🧠 {e.data.classifier}{e.data.reasoning ? ` — ${e.data.reasoning}` : ''}</div>}
              {e.data.evidence.map((ev, k) => (
                <div key={k}>
                  🔗 {/^https?:/.test(ev.link) ? <a href={ev.link} target="_blank" rel="noreferrer" className="text-sky-300 underline">{ev.title}</a> : ev.title}{' '}
                  <span className="text-slate-500">({ev.source})</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
      <div ref={end} />
    </div>
  )
}
