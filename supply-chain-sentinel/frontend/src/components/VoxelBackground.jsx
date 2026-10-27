import { useEffect, useRef } from 'react'
import { createScene } from '../lib/voxelScene'

export default function VoxelBackground() {
  const ref = useRef(null)
  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const scene = createScene(ref.current, { reduce, getSize: () => ({ w: window.innerWidth, h: window.innerHeight }) })
    scene.start()
    let timer
    const onResize = () => { clearTimeout(timer); timer = setTimeout(scene.resize, 120) }
    window.addEventListener('resize', onResize)
    return () => { scene.stop(); clearTimeout(timer); window.removeEventListener('resize', onResize) }
  }, [])
  return (
    <>
      <canvas ref={ref} aria-hidden="true" className="fixed inset-0 z-0 h-full w-full" style={{ imageRendering: 'pixelated' }} />
      <div className="mc-dim" aria-hidden="true" />
    </>
  )
}
