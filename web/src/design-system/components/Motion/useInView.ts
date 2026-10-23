import { useEffect, useRef, useState } from 'react'

export const prefersReducedMotion = (): boolean =>
  typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

const hasObserver = (): boolean => typeof IntersectionObserver !== 'undefined'

/**
 * True once the element has entered (or come near) the viewport. Without IntersectionObserver
 * (old browsers, jsdom) the content is treated as visible immediately: motion and lazy loading are
 * progressive enhancements and never gate content.
 *
 * `rootMargin` is the IntersectionObserver margin. A passive scroll/resize check with the same
 * look-ahead (`lookAheadPx`, negative = reveal a little later) runs alongside it as a fail-safe, so a
 * browser that delays or drops observer callbacks can never leave content invisible.
 */
export function useInView<T extends Element>(rootMargin = '0px 0px -8% 0px', lookAheadPx = -48) {
  const ref = useRef<T>(null)
  const [inView, setInView] = useState(() => !hasObserver())

  useEffect(() => {
    const element = ref.current
    if (!element || !hasObserver()) {
      setInView(true)
      return
    }
    let done = false
    let frame = 0
    const reveal = () => {
      if (done) return
      done = true
      setInView(true)
      cleanup()
    }
    const check = () => {
      frame = 0
      const rect = element.getBoundingClientRect()
      if (rect.bottom > 0 && rect.top < window.innerHeight + lookAheadPx) reveal()
    }
    const schedule = () => {
      if (!frame && !done) frame = requestAnimationFrame(check)
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) reveal()
      },
      { rootMargin },
    )
    function cleanup() {
      observer.disconnect()
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      if (frame) cancelAnimationFrame(frame)
    }
    observer.observe(element)
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    schedule()
    return () => {
      done = true
      cleanup()
    }
  }, [rootMargin, lookAheadPx])

  return { ref, inView }
}
