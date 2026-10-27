import { useState } from 'react'

const input = 'w-full rounded-xl border border-slate-600/60 bg-slate-950/60 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-400/30'

export default function AuthPage({ onLogin, onSignup, onGuest }) {
  const [mode, setMode] = useState('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const signup = mode === 'signup'

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (signup) await onSignup(name, email, password)
      else await onLogin(email, password)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const switchMode = () => { setMode(signup ? 'login' : 'signup'); setError('') }

  return (
    <div className="grid min-h-screen place-items-center px-4 py-10">
      <div className="anim-slide-in w-full max-w-md">
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="float text-6xl drop-shadow-[0_0_30px_rgba(56,189,248,.6)]">🛰️</div>
          <h1 className="gradient-text brand-title mt-3 text-3xl font-extrabold">Supply Chain Sentinel</h1>
          <p className="hero-copy mt-1 text-sm text-slate-400">Autonomous supply-chain disruption response</p>
        </div>

        <form onSubmit={submit} className="glass rounded-3xl p-7">
          <h2 className="text-xl font-bold text-slate-100">{signup ? 'Create your account' : 'Welcome back'}</h2>
          <p className="mb-5 mt-1 text-sm text-slate-400">{signup ? 'Takes five seconds — no email verification.' : 'Sign in to run live disruptions.'}</p>

          <div className="flex flex-col gap-3">
            {signup && <input className={input} placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />}
            <input className={input} type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
            <div className="relative">
              <input className={`${input} pr-16`} type={show ? 'text' : 'password'} placeholder="Password (min 6 characters)" value={password}
                onChange={(e) => setPassword(e.target.value)} autoComplete={signup ? 'new-password' : 'current-password'} required />
              <button type="button" onClick={() => setShow(!show)} className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-slate-400 hover:text-sky-300">
                {show ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>

          {error && <div className="anim-slide-in mt-4 rounded-lg border border-red-500/60 bg-red-500/10 p-3 text-sm text-red-200">{error}</div>}

          <button type="submit" disabled={busy}
            className="btn-glow mt-5 w-full rounded-xl bg-gradient-to-r from-sky-400 to-cyan-300 py-3 text-sm font-bold text-slate-950 disabled:cursor-wait disabled:opacity-60">
            {busy ? 'Please wait…' : signup ? 'Create account' : 'Sign in'}
          </button>

          <div className="my-4 flex items-center gap-3 text-xs text-slate-500">
            <span className="h-px flex-1 bg-slate-700" /> or <span className="h-px flex-1 bg-slate-700" />
          </div>

          <button type="button" onClick={onGuest}
            className="btn-glow w-full rounded-xl border border-slate-500/60 bg-white/5 py-3 text-sm font-semibold text-slate-100">
            ▶ Continue as guest (offline demo)
          </button>

          <p className="mt-5 text-center text-sm text-slate-400">
            {signup ? 'Already have an account?' : 'New here?'}{' '}
            <button type="button" onClick={switchMode} className="font-semibold text-sky-300 hover:underline">
              {signup ? 'Sign in' : 'Create an account'}
            </button>
          </p>
        </form>
      </div>
    </div>
  )
}
