import { useCallback, useEffect, useState } from 'react'
import { useRun } from './lib/useRun'
import { authFetch, useAuth } from './lib/auth'
import LiveBackground from './components/LiveBackground'
import VoxelBackground from './components/VoxelBackground'
import AuthPage from './components/AuthPage'
import PlanFeed from './components/PlanFeed'
import PipelineStrip from './components/PipelineStrip'
import TradeOffTable from './components/TradeOffTable'
import NegotiationLoopView from './components/NegotiationLoopView'
import TraceLog from './components/TraceLog'
import FinalPlanView from './components/FinalPlanView'
import SupplierInbox from './components/SupplierInbox'

function Card({ title, children, delay = 0 }) {
  return (
    <section className="glass anim-slide-in rounded-2xl p-5" style={{ animationDelay: `${delay}ms` }}>
      <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-sky-300/80">
        <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />
        {title}
      </h2>
      {children}
    </section>
  )
}

const STEPS = [
  { i: '📡', t: 'Detect', d: 'The Monitor Agent spots a disruption — a port closure, a factory fire — without anyone asking.' },
  { i: '📊', t: 'Assess', d: 'The Impact Agent finds every order and customer at risk and ranks them by urgency.' },
  { i: '🔎', t: 'Source & negotiate', d: 'Sourcing scores alternate suppliers; Negotiation drafts the outreach and sends it via n8n.' },
  { i: '⚖️', t: 'Enforce policy', d: 'The Budget Agent can reject a plan and force re-sourcing — until a compliant plan is approved.' },
]

export default function App() {
  const auth = useAuth()
  const signedIn = !!auth.user
  const inApp = signedIn || auth.guest

  // theme: 'craft' (pixel/blocky, default) or 'neon' (glass). Remembered between visits.
  const [theme, setTheme] = useState(() => { try { return localStorage.getItem('sentinel_theme') || 'craft' } catch { return 'craft' } })
  useEffect(() => {
    document.documentElement.classList.toggle('craft', theme === 'craft')
    try { localStorage.setItem('sentinel_theme', theme) } catch { /* ignore */ }
  }, [theme])

  return (
    <div className="relative min-h-screen text-slate-100">
      {theme === 'craft' ? <VoxelBackground /> : <LiveBackground />}
      <div className="relative z-10">
        {inApp ? (
          <Dashboard auth={auth} />
        ) : (
          <AuthPage onLogin={auth.login} onSignup={auth.signup} onGuest={auth.enterGuest} />
        )}
      </div>
      <button onClick={() => setTheme(theme === 'craft' ? 'neon' : 'craft')} title="Switch theme"
        className="btn-glow fixed bottom-3 left-3 z-30 rounded-xl border border-slate-500/60 bg-slate-900/80 px-3 py-2 text-xs font-semibold text-slate-100 backdrop-blur">
        {theme === 'craft' ? '✨ Neon theme' : '🧱 Craft theme'}
      </button>
    </div>
  )
}

function Dashboard({ auth }) {
  const live = !!auth.user
  const [plans, setPlans] = useState([])
  const refresh = useCallback(() => {
    if (!live) return
    authFetch('/api/plans').then((r) => (r.ok ? r.json() : [])).then(setPlans).catch(() => {})
  }, [live])
  const { run, startLive, startDemo, attach, override } = useRun(refresh)
  const [pick, setPick] = useState('')
  const [ai, setAi] = useState(null)
  const [n8n, setN8n] = useState(null)

  useEffect(() => {
    if (!live) return
    authFetch('/api/system/status').then((r) => (r.ok ? r.json() : null)).then((d) => { if (d) { setAi(d.llm); setN8n(d.n8n) } }).catch(() => {})
  }, [live])

  useEffect(() => {
    refresh()
    if (!live) return
    const t = setInterval(refresh, 3000)
    return () => clearInterval(t)
  }, [refresh, live])

  const busy = run.running
  const idle = run.status === 'idle'
  const btn = 'btn-glow rounded-xl px-5 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40'

  const Buttons = (
    <div className="flex flex-wrap justify-center gap-2">
      <button disabled={busy || !live} title={live ? '' : 'Sign in to run live disruptions'} onClick={() => startLive('port_closure')}
        className={`${btn} bg-gradient-to-r from-sky-400 to-cyan-300 text-slate-950`}>⚓ Trigger port closure</button>
      <button disabled={busy || !live} title={live ? '' : 'Sign in to run live disruptions'} onClick={() => startLive('factory_fire')}
        className={`${btn} bg-gradient-to-r from-amber-400 to-orange-400 text-slate-950`}>🔥 Trigger factory fire</button>
      <button disabled={busy || !live} title={live ? 'Scans real news + weather for your supply nodes (falls back to the scripted event if nothing is found)' : 'Sign in to run live disruptions'} onClick={() => startLive('live_scan')}
        className={`${btn} bg-gradient-to-r from-violet-400 to-fuchsia-400 text-slate-950`}>📡 Live scan</button>
      <button disabled={busy} onClick={startDemo} className={`${btn} border border-slate-500/60 bg-white/5 text-slate-100 backdrop-blur`}>▶ Run demo (no backend)</button>
    </div>
  )

  return (
    <>
      <header className="glass sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 border-x-0 border-t-0 px-6 py-3">
        <div className="flex items-center gap-3">
          <span className="text-3xl">🛰️</span>
          <div>
            <h1 className="gradient-text brand-title text-xl font-extrabold leading-tight">Supply Chain Sentinel</h1>
            <p className="text-xs text-slate-400">Autonomous disruption response · live agent trace</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {!idle && Buttons}
          {n8n && (
            <div title="Automation layer that delivers outreach and notifications" className="hidden rounded-xl border border-slate-600/50 bg-white/5 px-3 py-1.5 text-xs text-slate-300 md:block">
              ⚙️ {n8n.reachable ? 'n8n connected' : n8n.configured ? 'n8n unreachable' : 'n8n mock mode'}
            </div>
          )}
          {ai && (
            <div title="Language model used by the agents" className="hidden rounded-xl border border-slate-600/50 bg-white/5 px-3 py-1.5 text-xs text-slate-300 md:block">
              🧠 {ai.configured ? `${ai.provider} · ${ai.model}` : 'Rules mode (no LLM key)'}
            </div>
          )}
          <div className="flex items-center gap-2 rounded-xl border border-slate-600/50 bg-white/5 py-1.5 pl-3 pr-1.5 text-sm">
            <span className="text-slate-200">👤 {live ? auth.user.name : 'Guest'}</span>
            <button onClick={auth.logout} className="rounded-lg bg-slate-700/60 px-3 py-1 text-xs font-semibold text-slate-100 hover:bg-slate-600">
              {live ? 'Log out' : 'Sign in'}
            </button>
          </div>
        </div>
      </header>

      <div className={idle ? 'mx-auto max-w-6xl px-6 py-6' : 'grid gap-6 p-6 lg:grid-cols-[270px_1fr]'}>
        {!idle && (
          <aside className="lg:sticky lg:top-24 lg:self-start">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Plans</h2>
            <PlanFeed plans={plans} selected={run.planId} onSelect={attach} />
          </aside>
        )}

        <main className="flex min-w-0 flex-col gap-6">
          {run.error && (
            <div className="anim-slide-in rounded-xl border border-red-500/60 bg-red-500/10 p-3 text-sm text-red-200 backdrop-blur">{run.error}</div>
          )}

          {idle ? (
            <div className="flex flex-col items-center py-8 text-center">
              <div className="float text-7xl drop-shadow-[0_0_30px_rgba(56,189,248,.6)]">🛰️</div>
              <h2 className="gradient-text hero-title mt-5 text-4xl font-extrabold md:text-6xl">Supply chains that fix themselves</h2>
              <div className="splash">Fully autonomous!</div>
              <p className="hero-copy mt-4 max-w-2xl text-base text-slate-300 md:text-lg">
                Five autonomous agents detect a disruption, work out what it breaks, find a replacement, negotiate it,
                and get it past budget policy — with no human in the loop.
              </p>
              <div className="mt-8">{Buttons}</div>
              <p className="mt-3 text-xs text-slate-500">
                {live ? 'Tip: start with “Run demo” — it works even if the backend is off.' : 'You’re in guest mode: sign in to run live disruptions through the real agents.'}
              </p>

              <div className="mt-14 grid w-full gap-4 text-left md:grid-cols-2 xl:grid-cols-4">
                {STEPS.map((s, i) => (
                  <div key={s.t} className="glass anim-slide-in rounded-2xl p-5" style={{ animationDelay: `${i * 120}ms` }}>
                    <div className="mb-2 flex items-center gap-2">
                      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-sky-500/20 text-xs font-bold text-sky-300">{i + 1}</span>
                      <span className="text-2xl">{s.i}</span>
                    </div>
                    <h3 className="font-semibold text-slate-100">{s.t}</h3>
                    <p className="mt-1 text-sm text-slate-400">{s.d}</p>
                  </div>
                ))}
              </div>

              {plans.length > 0 && (
                <div className="mt-12 w-full text-left">
                  <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Recent plans</h2>
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    <PlanFeed plans={plans.slice(0, 6)} selected={run.planId} onSelect={attach} />
                  </div>
                </div>
              )}
            </div>
          ) : (
            <>
              <Card title={`Agent pipeline — ${run.status}${run.mode === 'demo' ? ' (offline demo)' : ''}`}>
                <PipelineStrip entries={run.entries} status={run.status} />
              </Card>

              <Card title="Negotiation loop (Budget ⇄ Sourcing)" delay={80}>
                <NegotiationLoopView history={run.history} status={run.status} />
              </Card>

              <Card title="Supplier trade-off table" delay={160}>
                <TradeOffTable shortlist={run.shortlist} planStatus={run.status} />
              </Card>

              <Card title="Supplier inbox — outreach delivered by n8n" delay={200}>
                <SupplierInbox outbox={run.outbox} />
              </Card>

              <FinalPlanView plan={run.final} attempts={run.history.length} />

              {run.status === 'escalated' && run.mode === 'live' && (
                <Card title="Human override required">
                  <p className="mb-3 text-sm text-slate-300">The agents exhausted their attempts. Pick a supplier to approve manually.</p>
                  <div className="flex flex-wrap gap-2">
                    <select value={pick} onChange={(e) => setPick(e.target.value)} className="rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm">
                      <option value="">Choose supplier…</option>
                      {run.shortlist.map((s) => (
                        <option key={s.supplier_id} value={s.supplier_id}>{s.name} (₹{s.unit_price}, {s.lead_time_days}d)</option>
                      ))}
                    </select>
                    <button disabled={!pick} onClick={() => override(pick, 'Approved by team lead')} className={`${btn} bg-emerald-400 text-slate-950`}>Approve override</button>
                  </div>
                </Card>
              )}

              <Card title="Live agent trace" delay={240}>
                <TraceLog entries={run.entries} />
              </Card>
            </>
          )}
        </main>
      </div>
    </>
  )
}
