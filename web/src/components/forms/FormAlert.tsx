import type { ReactNode } from 'react'

interface FormAlertProps {
  kind: 'error' | 'success' | 'info'
  children: ReactNode
}

export function FormAlert({ kind, children }: FormAlertProps) {
  return (
    <div className={`alert alert--${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  )
}
