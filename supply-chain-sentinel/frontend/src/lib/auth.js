import { useCallback, useEffect, useState } from 'react'

const TOKEN_KEY = 'sentinel_token'
const USER_KEY = 'sentinel_user'

export const getToken = () => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } }
const save = (token, user) => { try { localStorage.setItem(TOKEN_KEY, token); localStorage.setItem(USER_KEY, JSON.stringify(user)) } catch { /* ignore */ } }
const clear = () => { try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY) } catch { /* ignore */ } }

// fetch that attaches the login token; a 401 anywhere logs the user out
export async function authFetch(url, opts = {}) {
  const t = getToken()
  const headers = { ...(opts.headers || {}), ...(t ? { Authorization: `Bearer ${t}` } : {}) }
  const res = await fetch(url, { ...opts, headers })
  if (res.status === 401) window.dispatchEvent(new Event('sentinel-unauthorized'))
  return res
}

async function post(path, body) {
  let res
  try {
    res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  } catch {
    throw new Error('Cannot reach the backend. Start it, or continue as guest for the offline demo.')
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${res.status}) - is the backend running?`)
  return data
}

export function useAuth() {
  const [user, setUser] = useState(() => {
    try { const u = localStorage.getItem(USER_KEY); return getToken() && u ? JSON.parse(u) : null } catch { return null }
  })
  const [guest, setGuest] = useState(false)

  const logout = useCallback(() => { clear(); setUser(null); setGuest(false) }, [])
  useEffect(() => {
    window.addEventListener('sentinel-unauthorized', logout)
    return () => window.removeEventListener('sentinel-unauthorized', logout)
  }, [logout])

  const login = async (email, password) => { const d = await post('/api/auth/login', { email, password }); save(d.token, d.user); setUser(d.user) }
  const signup = async (name, email, password) => { const d = await post('/api/auth/signup', { name, email, password }); save(d.token, d.user); setUser(d.user) }

  return { user, guest, login, signup, logout, enterGuest: () => setGuest(true) }
}
