import type { CSSProperties, ElementType, HTMLAttributes, ReactNode } from 'react'

import styles from './Motion.module.css'
import { useInView } from './useInView'

export interface RevealProps extends HTMLAttributes<HTMLElement> {
  as?: ElementType
  /** Stagger index: each step delays the entrance by 70ms (capped). */
  index?: number
  children: ReactNode
}

/**
 * Gentle entrance (fade + 14px rise) the first time a block scrolls into view. Pure CSS transition;
 * `prefers-reduced-motion` shows the content immediately. Never hides content when JS or
 * IntersectionObserver is unavailable.
 */
export function Reveal({ as: Tag = 'div', index = 0, className = '', style, children, ...rest }: RevealProps) {
  const { ref, inView } = useInView<HTMLElement>()
  const delay = Math.min(index, 6) * 70
  return (
    <Tag
      {...rest}
      ref={ref}
      className={`${styles.reveal} ${inView ? styles.in : ''} ${className}`.trim()}
      style={{ ...(style as CSSProperties), '--reveal-delay': `${delay}ms` } as CSSProperties}
    >
      {children}
    </Tag>
  )
}

/** Mounts `children` (and so starts their data loading) only when the block nears the viewport. */
export function NearViewport({ children, minHeight = '14rem', rootMargin = '0px 0px 320px 0px' }: { children: ReactNode; minHeight?: string; rootMargin?: string }) {
  const { ref, inView } = useInView<HTMLDivElement>(rootMargin, 320)
  return (
    <div ref={ref} style={inView ? undefined : { minBlockSize: minHeight }}>
      {inView ? children : null}
    </div>
  )
}
