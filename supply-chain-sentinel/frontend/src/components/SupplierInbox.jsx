const badge = (s = '') =>
  s.includes('delivered') ? 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-400/50'
  : s.includes('mock') || s.includes('unreachable') ? 'bg-amber-500/20 text-amber-300 ring-1 ring-amber-400/50'
  : 'bg-sky-500/20 text-sky-300 ring-1 ring-sky-400/50'

// Emails the Negotiation Agent drafted. n8n delivers them; the status shows whether it really did.
export default function SupplierInbox({ outbox }) {
  if (!outbox || outbox.length === 0) return <p className="text-sm text-slate-500">No outreach sent yet.</p>
  return (
    <div className="flex flex-col gap-3">
      {outbox.map((m) => (
        <details key={m.attempt} open={m.attempt === outbox.length} className="anim-slide-in rounded-lg border border-slate-600/50 bg-black/20 p-3">
          <summary className="cursor-pointer text-sm">
            <span className="font-semibold text-slate-100">To {m.supplier}</span>
            <span className="text-slate-400"> — {m.subject}</span>
            <span className={`ml-2 rounded-full px-2 py-0.5 text-xs ${badge(m.status)}`}>{m.status}</span>
          </summary>
          {m.to && <div className="mt-2 text-xs text-slate-400">to: {m.to}</div>}
          <pre className="mt-2 whitespace-pre-wrap font-mono text-xs text-slate-300">{m.body}</pre>
          {m.n8n_execution_id && <div className="mt-1 text-[11px] text-slate-500">n8n execution: {m.n8n_execution_id}</div>}
        </details>
      ))}
    </div>
  )
}
