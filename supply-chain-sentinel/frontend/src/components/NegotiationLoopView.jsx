// The demo centerpiece: each Sourcing<->Budget round trip is a card. A rejection shakes + flashes,
// then a "back to Sourcing" connector leads to the next attempt.
export default function NegotiationLoopView({ history, status }) {
  if (!history || history.length === 0) {
    return <p className="text-sm text-slate-500">No budget review yet.</p>
  }
  return (
    <div className="flex flex-col gap-2">
      {history.map((h, i) => {
        const rejected = h.decision === 'reject'
        return (
          <div key={h.attempt}>
            <div className={`rounded-xl border p-4 ${rejected ? 'anim-reject border-red-500/60 bg-red-500/10' : 'anim-slide-in border-emerald-500/60 bg-emerald-500/10'}`}>
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-slate-100">
                  Attempt {h.attempt} · {h.supplier}
                </div>
                <span className={`rounded-full px-3 py-0.5 text-xs font-bold ${rejected ? 'bg-red-500 text-white' : 'bg-emerald-500 text-white'}`}>
                  {rejected ? 'REJECTED' : 'APPROVED'}
                </span>
              </div>
              <div className="mt-2 text-sm text-slate-300">{h.reason}</div>
              <div className="mt-1 text-xs text-slate-400">Policy rule: <span className="font-mono">{h.rule}</span></div>
            </div>
            {rejected && (
              <div className="anim-slide-in my-1 ml-6 flex items-center gap-2 text-sm text-amber-300">
                <span className="text-xl">↩</span>
                {i === history.length - 1 && status === 'escalated'
                  ? 'Attempts exhausted — escalated to a human'
                  : 'Back to Sourcing with the rejection reason attached → next-best supplier'}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
