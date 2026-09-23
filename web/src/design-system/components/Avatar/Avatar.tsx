import type { ReactNode } from 'react'

import styles from './Avatar.module.css'

export interface AvatarProps {
  /** https image; falls back to initials / icon. */
  src?: string | null
  name: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  /** Shown instead of initials when there is no image (e.g. a type icon). */
  fallback?: ReactNode
  className?: string
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const first = parts[0]?.[0] ?? ''
  const second = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : ''
  return (first + second).toUpperCase()
}

export function Avatar({ src, name, size = 'md', fallback, className = '' }: AvatarProps) {
  const sizeClass = size !== 'md' ? styles[size] : ''
  return (
    <span className={`${styles.avatar} ${sizeClass} ${className}`.trim()} aria-hidden={src ? undefined : true}>
      {src ? <img className={styles.image} src={src} alt="" loading="lazy" /> : (fallback ?? initials(name))}
    </span>
  )
}
