import type { ReactNode } from 'react'

import { Spinner } from './Spinner'

interface LoadingOverlayProps {
  active: boolean
  label?: string
  children?: ReactNode
}

/** Dims its children and shows a spinner while `active`. Blocks interaction. */
export function LoadingOverlay({ active, label, children }: LoadingOverlayProps) {
  return (
    <div className="overlay-host" aria-busy={active}>
      <div className="overlay-host__content" inert={active || undefined}>
        {children}
      </div>
      {active && (
        <div className="overlay" data-testid="loading-overlay">
          <Spinner size="lg" label={label} />
        </div>
      )}
    </div>
  )
}
