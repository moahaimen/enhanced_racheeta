import type { ReactNode } from 'react'

import { Icon } from '../../icons'
import styles from './Alert.module.css'

export type AlertKind = 'error' | 'success' | 'warning' | 'info'

export interface AlertProps {
  kind: AlertKind
  title?: ReactNode
  children: ReactNode
  className?: string
}

const ICONS = { error: 'alertCircle', success: 'checkCircle', warning: 'alertCircle', info: 'info' } as const

/** Inline feedback. Errors are announced (role=alert); the rest are polite status. */
export function Alert({ kind, title, children, className = '' }: AlertProps) {
  return (
    <div className={`${styles.alert} ${styles[kind]} ${className}`.trim()} role={kind === 'error' ? 'alert' : 'status'}>
      <Icon name={ICONS[kind]} className={styles.icon} />
      <div className={styles.body}>
        {title ? <div className={styles.title}>{title}</div> : null}
        <div>{children}</div>
      </div>
    </div>
  )
}

/** Backwards-compatible name used by the auth pages. */
export function FormAlert({ kind, children }: { kind: 'error' | 'success' | 'info'; children: ReactNode }) {
  return <Alert kind={kind}>{children}</Alert>
}
