import { useEffect, useState } from 'react'

import { prefersReducedMotion, useInView } from './useInView'

/** Counts from 0 to a REAL value when it enters the viewport; static when motion is reduced. */
export function CountUp({ value, locale, durationMs = 900 }: { value: number; locale: string; durationMs?: number }) {
  const { ref, inView } = useInView<HTMLSpanElement>()
  const [shown, setShown] = useState<number | null>(null)
  const animate = inView && !prefersReducedMotion() && typeof requestAnimationFrame !== 'undefined'

  useEffect(() => {
    if (!animate) return
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / durationMs)
      setShown(Math.round(value * (1 - Math.pow(1 - progress, 3))))
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [animate, value, durationMs])

  // Before the first animation frame an animating counter reads 0; otherwise the real value.
  const display = animate ? (shown ?? 0) : value
  return (
    <span ref={ref} aria-label={value.toLocaleString(locale)}>
      <span aria-hidden="true">{display.toLocaleString(locale)}</span>
    </span>
  )
}
