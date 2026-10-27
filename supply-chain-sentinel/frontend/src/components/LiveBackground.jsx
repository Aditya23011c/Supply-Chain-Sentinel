import { useEffect, useRef } from 'react'

// Live wallpaper: a drifting supply-chain network. Packets (goods) flow along routes; every few seconds
// a node is "disrupted" (red shockwave) and the network "reroutes" (green pulse) - the product story, as wallpaper.
export default function LiveBackground() {
  const ref = useRef(null)

  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas.getContext('2d')
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const rand = (a, b) => a + Math.random() * (b - a)
    let w = 0, h = 0, dpr = 1, raf = 0
    let nodes = [], packets = [], pulses = []
    let lastAlert = performance.now() - 3500
    const timeouts = []

    function build() {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = canvas.width = Math.floor(window.innerWidth * dpr)
      h = canvas.height = Math.floor(window.innerHeight * dpr)
      canvas.style.width = window.innerWidth + 'px'
      canvas.style.height = window.innerHeight + 'px'
      const count = Math.round(Math.min(52, Math.max(24, (window.innerWidth * window.innerHeight) / 30000)))
      nodes = Array.from({ length: count }, () => ({
        x: rand(0, w), y: rand(0, h),
        vx: rand(-0.14, 0.14) * dpr, vy: rand(-0.14, 0.14) * dpr,
        r: rand(1.8, 3.6) * dpr, hub: Math.random() < 0.18, alert: 0, heal: 0,
      }))
      packets = []
      pulses = []
    }

    function frame(now) {
      ctx.clearRect(0, 0, w, h)
      const maxD = 210 * dpr
      const edges = []

      for (const n of nodes) {
        n.x += n.vx; n.y += n.vy
        if (n.x < 0 || n.x > w) n.vx *= -1
        if (n.y < 0 || n.y > h) n.vy *= -1
        n.alert = Math.max(0, n.alert - 0.006)
        n.heal = Math.max(0, n.heal - 0.012)
      }

      // routes
      ctx.lineWidth = 1 * dpr
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j]
          const d = Math.hypot(a.x - b.x, a.y - b.y)
          if (d < maxD) {
            edges.push([i, j])
            const broken = a.alert > 0.05 || b.alert > 0.05
            const alpha = (1 - d / maxD) * (broken ? 0.45 : 0.22)
            ctx.strokeStyle = broken ? `rgba(248,113,113,${alpha})` : `rgba(56,189,248,${alpha})`
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke()
          }
        }
      }

      // goods flowing along routes
      if (edges.length && packets.length < 70 && Math.random() < 0.16) {
        const [a, b] = edges[Math.floor(Math.random() * edges.length)]
        packets.push(Math.random() < 0.5 ? { a, b, t: 0, s: rand(0.004, 0.011) } : { a: b, b: a, t: 0, s: rand(0.004, 0.011) })
      }
      for (let k = packets.length - 1; k >= 0; k--) {
        const p = packets[k]
        p.t += p.s
        if (p.t >= 1) { packets.splice(k, 1); continue }
        const a = nodes[p.a], b = nodes[p.b]
        const x = a.x + (b.x - a.x) * p.t, y = a.y + (b.y - a.y) * p.t
        const bad = a.alert > 0.05 || b.alert > 0.05
        ctx.shadowBlur = 14 * dpr
        ctx.shadowColor = bad ? 'rgba(248,113,113,.9)' : 'rgba(52,211,153,.9)'
        ctx.fillStyle = bad ? '#fca5a5' : '#6ee7b7'
        ctx.beginPath(); ctx.arc(x, y, 2 * dpr, 0, Math.PI * 2); ctx.fill()
        ctx.shadowBlur = 0
      }

      // nodes
      for (const n of nodes) {
        let color = n.hub ? '167,139,250' : '125,211,252'
        if (n.alert > 0.05) color = '248,113,113'
        else if (n.heal > 0.05) color = '52,211,153'
        ctx.shadowBlur = (n.hub ? 18 : 10) * dpr
        ctx.shadowColor = `rgba(${color},.9)`
        ctx.fillStyle = `rgba(${color},.95)`
        ctx.beginPath(); ctx.arc(n.x, n.y, n.hub ? n.r * 1.6 : n.r, 0, Math.PI * 2); ctx.fill()
        ctx.shadowBlur = 0
      }

      // shockwaves
      for (let k = pulses.length - 1; k >= 0; k--) {
        const p = pulses[k]
        p.r += 3.2 * dpr
        const life = 1 - p.r / (p.max * dpr)
        if (life <= 0) { pulses.splice(k, 1); continue }
        ctx.strokeStyle = `rgba(${p.c},${life * 0.7})`
        ctx.lineWidth = 2 * dpr
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.stroke()
      }

      // disruption -> reroute story, every ~7s
      if (now - lastAlert > 7000 && nodes.length) {
        lastAlert = now
        const victim = nodes[Math.floor(Math.random() * nodes.length)]
        victim.alert = 1
        pulses.push({ x: victim.x, y: victim.y, r: 0, max: 230, c: '248,113,113' })
        timeouts.push(setTimeout(() => {
          let best = null, bd = Infinity
          for (const n of nodes) {
            if (n === victim) continue
            const d = Math.hypot(n.x - victim.x, n.y - victim.y)
            if (d < bd) { bd = d; best = n }
          }
          if (best) {
            best.heal = 1
            pulses.push({ x: best.x, y: best.y, r: 0, max: 200, c: '52,211,153' })
          }
          victim.alert = 0
          victim.heal = 1
        }, 1800))
      }

      if (!reduce) raf = requestAnimationFrame(frame)
    }

    build()
    if (reduce) frame(performance.now())
    else raf = requestAnimationFrame(frame)

    const onResize = () => build()
    window.addEventListener('resize', onResize)
    return () => {
      cancelAnimationFrame(raf)
      timeouts.forEach(clearTimeout)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  return (
    <>
      <div className="aurora" aria-hidden="true"><div className="aurora-grid" /></div>
      <canvas ref={ref} aria-hidden="true" className="pointer-events-none fixed inset-0 z-0" />
    </>
  )
}
