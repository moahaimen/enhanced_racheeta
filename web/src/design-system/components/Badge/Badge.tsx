import type { HTMLAttributes, ReactNode } from 'react'

import styles from './Badge.module.css'

export type BadgeTone = 'neutral' | 'brand' | 'success' | 'warning' | 'error' | 'info' | 'outline'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone
  leading?: ReactNode
  children: ReactNode
}

export function Badge({ tone = 'neutral', leading, className = '', children, ...rest }: BadgeProps) {
  const toneClass = tone !== 'neutral' ? styles[tone] : ''
  return (
    <span {...rest} className={`${styles.badge} ${toneClass} ${className}`.trim()}>
      {leading}
      {children}
    </span>
  )
}
