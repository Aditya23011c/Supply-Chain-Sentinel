// Pixel-art "live wallpaper": day/night cycle, blocky parallax hills, trees, clouds, stars, fireflies, rain.
// Renders to a LOW-RES canvas (about 100-190 px wide) that CSS scales up crisply => chunky blocks on any screen.
const CYCLE = 110 // seconds for one full day
const START = 0.12 * CYCLE // begin in the morning

const lerp = (a, b, t) => a + (b - a) * t
const clamp = (v, a, b) => Math.min(b, Math.max(a, v))
const mix = (c1, c2, t) => [lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t)]
const css = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`
function rng(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const C = {
  dayTop: [88, 150, 255], dayBot: [176, 214, 255], nightTop: [6, 8, 28], nightBot: [20, 26, 66],
  duskTop: [96, 62, 128], duskBot: [255, 150, 84],
  far: [[104, 150, 130], [18, 30, 44]], mid: [[74, 146, 74], [14, 36, 28]],
  grass: [[96, 176, 54], [20, 54, 26]], dirt: [[124, 86, 58], [40, 28, 22]], stone: [[122, 122, 122], [36, 36, 44]],
  trunk: [[104, 74, 42], [30, 22, 14]], leaves: [[50, 124, 42], [14, 42, 18]],
  cloudDay: [255, 255, 255], cloudNight: [62, 68, 98],
}
const LAYERS = [
  { base: 0.62, amp: 0.07, k1: 2, k2: 5, p1: 0.4, p2: 1.7, speed: 1.2 },
  { base: 0.73, amp: 0.055, k1: 3, k2: 7, p1: 2.1, p2: 0.3, speed: 2.6 },
  { base: 0.85, amp: 0.04, k1: 4, k2: 9, p1: 4.0, p2: 2.2, speed: 4.8 },
]

export function createScene(canvas, opts) {
  const ctx = canvas.getContext('2d')
  const reduce = !!opts.reduce
  let W = 0, H = 0, raf = 0, last = 0, t0 = 0
  let stars = [], trees = [], clouds = [], flies = [], drops = []
  const rain = { f: 0, target: 0, next: 28, until: 0 }
  const off = [0, 0, 0]

  const px = (x, y, w, h) => ctx.fillRect(Math.floor(x), Math.floor(y), Math.max(1, Math.floor(w)), Math.max(1, Math.floor(h)))
  const hh = (l, x) => {
    const a = (2 * Math.PI) / W
    return Math.round((H * l.base + H * l.amp * (Math.sin(a * l.k1 * x + l.p1) + 0.5 * Math.sin(a * l.k2 * x + l.p2))) / 2) * 2
  }

  function build() {
    const { w, h } = opts.getSize()
    const block = clamp(Math.round(w / 110), 4, 10) // CSS px per art pixel: smaller on phones
    W = Math.max(60, Math.ceil(w / block))
    H = Math.max(60, Math.ceil(h / block))
    canvas.width = W
    canvas.height = H
    const r = rng(1337)
    stars = Array.from({ length: Math.round((W * H) / 160) }, () => ({ x: Math.floor(r() * W), y: Math.floor(r() * H * 0.55), p: r() * 6.28, b: r() }))
    trees = Array.from({ length: Math.max(4, Math.round(W / 20)) }, () => ({ x: Math.floor(r() * W), h: 3 + Math.floor(r() * 3) }))
    clouds = Array.from({ length: Math.max(3, Math.round(W / 34)) }, () => ({ x: r() * W, y: Math.floor(H * (0.08 + r() * 0.28)), w: 6 + Math.floor(r() * 8), s: 0.8 + r() * 1.6 }))
    flies = Array.from({ length: Math.max(8, Math.round(W / 10)) }, () => ({ x: r() * W, y: H * (0.6 + r() * 0.3), p: r() * 6.28, s: 0.3 + r() }))
    drops = Array.from({ length: Math.round(W / 2.5) }, () => ({ x: r() * W, y: r() * H, v: 40 + r() * 30 }))
  }

  function draw(t, dt) {
    const phase = (t / CYCLE) % 1
    const ang = phase * 2 * Math.PI
    const s = Math.sin(ang)
    const dayF = clamp((s + 0.2) / 0.5, 0, 1)
    const nightF = 1 - dayF
    const duskF = 1 - clamp(Math.abs(s) / 0.28, 0, 1)

    // rain state machine
    if (!reduce) {
      if (rain.target === 0 && t > rain.next) { rain.target = 1; rain.until = t + 10 + Math.random() * 8 }
      else if (rain.target === 1 && t > rain.until) { rain.target = 0; rain.next = t + 45 + Math.random() * 40 }
      rain.f += (rain.target - rain.f) * Math.min(1, dt * 0.8)
    }
    const rainF = rain.f
    const grey = [70, 78, 100]

    // sky in chunky bands
    let top = mix(mix(C.nightTop, C.dayTop, dayF), C.duskTop, duskF * 0.7)
    let bot = mix(mix(C.nightBot, C.dayBot, dayF), C.duskBot, duskF * 0.8)
    top = mix(top, grey, rainF * 0.55)
    bot = mix(bot, grey, rainF * 0.45)
    const bands = 14, bh = Math.ceil(H / bands)
    for (let b = 0; b < bands; b++) { ctx.fillStyle = css(mix(top, bot, b / (bands - 1))); px(0, b * bh, W, bh + 1) }

    // stars
    for (const st of stars) {
      const a = nightF * (1 - rainF) * (0.5 + 0.5 * Math.sin(t * 2 + st.p))
      if (a < 0.05) continue
      ctx.fillStyle = `rgba(255,255,255,${a})`
      px(st.x, st.y, st.b > 0.92 ? 2 : 1, 1)
    }

    // sun + moon (square, of course)
    const sz = Math.max(5, Math.round(W * 0.04))
    const sx = W * 0.5 - Math.cos(ang) * W * 0.55, sy = H * 0.6 - s * H * 0.5
    if (sy < H) {
      ctx.fillStyle = css([255, 226, 90], 1 - rainF * 0.6); px(sx - sz / 2, sy - sz / 2, sz, sz)
      ctx.fillStyle = css([255, 246, 176], 1 - rainF * 0.6); px(sx - sz / 2 + 1, sy - sz / 2 + 1, sz - 2, sz - 2)
    }
    if (nightF > 0.05) {
      const mx = W * 0.5 + Math.cos(ang) * W * 0.55, my = H * 0.6 + s * H * 0.5
      ctx.fillStyle = css([226, 231, 242], nightF * (1 - rainF * 0.6)); px(mx - sz / 2, my - sz / 2, sz, sz)
      ctx.fillStyle = css([170, 178, 196], nightF * (1 - rainF * 0.6))
      px(mx - sz / 2 + 1, my - sz / 2 + 1, 2, 1); px(mx + 1, my, 1, 2); px(mx - 1, my + 1, 1, 1)
    }

    // clouds
    let cc = mix(C.cloudNight, C.cloudDay, dayF)
    cc = mix(mix(cc, [255, 190, 150], duskF * 0.4), [95, 100, 115], rainF * 0.8)
    ctx.fillStyle = css(cc, 0.95)
    for (const c of clouds) {
      c.x += c.s * dt
      if (c.x > W + c.w) c.x = -c.w
      px(c.x, c.y, c.w, 2); px(c.x + 2, c.y - 2, c.w - 5, 2); px(c.x - 1, c.y + 1, c.w + 2, 1)
    }

    // hills (parallax) + trees on the near layer
    const tint = (col, i) => {
      let c = mix(col[1], col[0], dayF)
      c = mix(c, [255, 170, 110], duskF * 0.18)
      return mix(c, grey, rainF * 0.22)
    }
    const far = tint(C.far), midc = tint(C.mid)
    const grass = tint(C.grass), dirt = tint(C.dirt), stone = tint(C.stone)
    const trunk = tint(C.trunk), leaves = tint(C.leaves)
    for (let i = 0; i < 3; i++) off[i] += LAYERS[i].speed * dt
    for (let i = 0; i < 3; i++) {
      const l = LAYERS[i], o = Math.floor(off[i])
      for (let x = 0; x < W; x++) {
        const y = hh(l, (x + o) % W)
        if (i === 2) {
          ctx.fillStyle = css(grass); px(x, y, 1, 1)
          ctx.fillStyle = css(dirt); px(x, y + 1, 1, 4)
          ctx.fillStyle = css(stone); px(x, y + 5, 1, H - y - 5)
        } else {
          ctx.fillStyle = css(i === 0 ? far : midc); px(x, y, 1, H - y)
          ctx.fillStyle = css(mix(i === 0 ? far : midc, [255, 255, 255], 0.12)); px(x, y, 1, 1)
        }
      }
    }
    const o2 = Math.floor(off[2])
    for (const tr of trees) {
      const x = (((tr.x - o2) % W) + W) % W, gy = hh(LAYERS[2], tr.x)
      ctx.fillStyle = css(trunk); px(x, gy - tr.h, 1, tr.h)
      ctx.fillStyle = css(leaves); px(x - 1, gy - tr.h - 2, 3, 2); px(x, gy - tr.h - 3, 1, 1)
    }

    // fireflies at night
    for (const f of flies) {
      const a = nightF * (1 - rainF) * (0.5 + 0.5 * Math.sin(t * 3 + f.p))
      if (a < 0.05) continue
      ctx.fillStyle = `rgba(220,255,120,${a})`
      px((((f.x + Math.sin(t * 0.4 * f.s + f.p) * 3) % W) + W) % W, f.y + Math.sin(t * 0.7 * f.s + f.p * 2) * 2, 1, 1)
    }

    // rain
    if (rainF > 0.05) {
      ctx.fillStyle = `rgba(150,180,255,${0.65 * rainF})`
      for (const d of drops) {
        d.y += d.v * dt
        if (d.y > H) { d.y = -2; d.x = Math.random() * W }
        px(d.x, d.y, 1, 2)
      }
    }
  }

  function loop(now) {
    raf = requestAnimationFrame(loop)
    if (now - last < 33) return // ~30 fps: retro feel, cheap on laptops/phones
    const dt = Math.min(0.1, (now - last) / 1000)
    last = now
    draw((now - t0) / 1000 + START, dt)
  }

  return {
    start() {
      build()
      t0 = performance.now(); last = 0
      if (reduce) draw(START, 0)
      else raf = requestAnimationFrame(loop)
    },
    stop() { cancelAnimationFrame(raf) },
    resize() { build(); if (reduce) draw(START, 0) },
    _draw: draw, _build: build,
  }
}
