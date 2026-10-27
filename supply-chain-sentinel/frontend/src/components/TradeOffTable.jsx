const BADGE = {
  pending: 'bg-slate-700/50 text-slate-300',
  proposed: 'bg-sky-500/20 text-sky-300 ring-1 ring-sky-400/50',
  rejected: 'bg-red-500/20 text-red-300 ring-1 ring-red-400/50',
  approved: 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-400/50',
}

export default function TradeOffTable({ shortlist, planStatus }) {
  if (!shortlist || shortlist.length === 0) {
    return <p className="text-sm text-slate-500">Waiting for the Sourcing Agent's shortlist…</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase text-slate-400">
          <tr>
            <th className="py-2 pr-3">Supplier</th><th className="pr-3">Location</th><th className="pr-3">Price / unit</th>
            <th className="pr-3">Lead time</th><th className="pr-3">Reliability</th><th className="pr-3">Score</th><th>Status</th>
          </tr>
        </thead>
        <tbody>
          {shortlist.map((s) => {
            const st = s.status === 'proposed' && planStatus === 'approved' ? 'approved' : s.status
            return (
              <tr key={s.supplier_id} className={`border-t border-slate-800 transition-colors duration-500 ${st === 'rejected' ? 'opacity-50' : ''} ${st === 'approved' ? 'bg-emerald-500/5' : ''}`}>
                <td className="py-2 pr-3 font-medium text-slate-100">{s.name}</td>
                <td className="pr-3 text-slate-300">{s.location}</td>
                <td className="pr-3 text-slate-300">₹{s.unit_price}</td>
                <td className="pr-3 text-slate-300">{s.lead_time_days}d</td>
                <td className="pr-3 text-slate-300">{Math.round(s.reliability * 100)}%</td>
                <td className="pr-3 text-slate-300">{s.score}</td>
                <td><span className={`rounded-full px-2 py-0.5 text-xs ${BADGE[st]}`}>{st}</span></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
