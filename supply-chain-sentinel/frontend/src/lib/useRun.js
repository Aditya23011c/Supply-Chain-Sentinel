import { useCallback, useEffect, useRef, useState } from 'react'
import { buildDemoSequence } from './dummy'
import { authFetch, getToken } from './auth'

const EMPTY = { planId: null, mode: null, entries: [], status: 'idle', history: [], shortlist: [], outbox: [], final: null, running: false, error: null }
const DEMO_STEP_MS = 1600

export function useRun(onChange) {
  const [run, setRun] = useState(EMPTY)
  const esRef = useRef(null)
  const timers = useRef([])

  const stop = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    timers.current.forEach(clearTimeout)
    timers.current = []
  }, [])
  useEffect(() => stop, [stop])

  const applyStage = (s) =>
    setRun((r) => ({
      ...r,
      entries: [...r.entries, s.entry],
      status: s.status,
      history: s.negotiation_history || r.history,
      shortlist: s.shortlist || r.shortlist,
      outbox: s.outbox || r.outbox,
    }))

  // Attach to a plan's SSE stream. Works for running AND finished plans (the backend replays history).
  const attach = useCallback((planId) => {
    stop()
    setRun({ ...EMPTY, planId, mode: 'live', running: true, status: 'monitoring' })
    const es = new EventSource(`/api/plans/${planId}/stream?token=${encodeURIComponent(getToken() || '')}`)
    esRef.current = es
    es.addEventListener('stage', (e) => applyStage(JSON.parse(e.data)))
    es.addEventListener('done', (e) => {
      const plan = JSON.parse(e.data)
      setRun((r) => ({ ...r, final: plan, status: plan.status, running: false, outbox: plan.outbox || r.outbox }))
      es.close()
      onChange?.()
    })
    es.onerror = () => {
      es.close()
      setRun((r) => (r.running ? { ...r, running: false, error: 'Stream disconnected - is the backend still running?' } : r))
    }
  }, [stop, onChange])

  const startLive = useCallback(async (kind) => {
    try {
      const res = await authFetch('/api/events/trigger', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const { plan_id } = await res.json()
      attach(plan_id)
      onChange?.()
    } catch (err) {
      stop()
      setRun({ ...EMPTY, error: `Could not reach the backend on :8000 (${err.message}). Start uvicorn, or use "Run demo (no backend)".` })
    }
  }, [attach, stop, onChange])

  const startDemo = useCallback(() => {
    stop()
    const { steps, final } = buildDemoSequence()
    setRun({ ...EMPTY, planId: 'demo_plan', mode: 'demo', running: true, status: 'monitoring' })
    steps.forEach((s, i) => timers.current.push(setTimeout(() => applyStage(s), (i + 1) * DEMO_STEP_MS)))
    timers.current.push(setTimeout(() => setRun((r) => ({ ...r, final, running: false })), (steps.length + 1) * DEMO_STEP_MS))
  }, [stop])

  const override = useCallback(async (supplierId, note) => {
    if (!run.planId) return
    const res = await authFetch(`/api/plans/${run.planId}/override`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'approve', supplier_id: supplierId, note }),
    })
    if (!res.ok) { setRun((r) => ({ ...r, error: `Override failed (HTTP ${res.status})` })); return }
    const plan = await res.json()
    setRun((r) => ({
      ...r, final: plan, status: plan.status, error: null,
      entries: [...r.entries, ...plan.trace.slice(r.entries.length)],
    }))
    onChange?.()
  }, [run.planId, onChange])

  return { run, startLive, startDemo, attach, override }
}
