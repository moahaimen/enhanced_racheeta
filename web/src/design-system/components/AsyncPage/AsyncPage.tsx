import type { DependencyList, ReactNode } from 'react'

import { useAsyncData } from '../../../hooks/useAsync'
import { ErrorState, LoadingState } from '../States/States'

export interface AsyncPageProps<T> {
  /** Backend loader. Receives an AbortSignal that fires on unmount. */
  load: (signal: AbortSignal) => Promise<T>
  deps?: DependencyList
  children: (data: T, reload: () => void) => ReactNode
  loadingLabel?: string
  /** Custom loading UI (e.g. skeleton cards) instead of the default spinner state. */
  skeleton?: ReactNode
}

/**
 * Wraps any page or block that loads backend data: visible loading state,
 * error state with retry, then renders children with the data.
 */
export function AsyncPage<T>({ load, deps = [], children, loadingLabel, skeleton }: AsyncPageProps<T>) {
  const { data, loading, error, reload } = useAsyncData(load, deps)

  if (loading) {
    return skeleton ? <div data-testid="async-loading">{skeleton}</div> : <LoadingState label={loadingLabel} testId="async-loading" />
  }
  if (error !== null || data === undefined) {
    return <ErrorState error={error} onRetry={reload} testId="async-error" />
  }
  return <>{children(data, reload)}</>
}
