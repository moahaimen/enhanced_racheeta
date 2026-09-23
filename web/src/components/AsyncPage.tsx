import type { DependencyList, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { toErrorMessage, useAsyncData } from '../hooks/useAsync'
import { Spinner } from './Spinner'

interface AsyncPageProps<T> {
  /** Backend loader. Receives an AbortSignal that fires on unmount. */
  load: (signal: AbortSignal) => Promise<T>
  deps?: DependencyList
  children: (data: T, reload: () => void) => ReactNode
  loadingLabel?: string
}

/**
 * Wraps any page that loads backend data: visible loading state, error state
 * with retry, then renders children with the data.
 */
export function AsyncPage<T>({ load, deps = [], children, loadingLabel }: AsyncPageProps<T>) {
  const { t } = useTranslation()
  const { data, loading, error, reload } = useAsyncData(load, deps)

  if (loading) {
    return (
      <div className="async-state" data-testid="async-loading">
        <Spinner size="lg" label={loadingLabel} />
        <p>{loadingLabel ?? t('common.loading')}</p>
      </div>
    )
  }
  if (error !== null || data === undefined) {
    return (
      <div className="async-state async-state--error" role="alert" data-testid="async-error">
        <p>
          <strong>{t('common.error')}</strong>
        </p>
        <p>{toErrorMessage(error, t('errors.unknown'))}</p>
        <button type="button" className="btn" onClick={reload}>
          {t('common.retry')}
        </button>
      </div>
    )
  }
  return <>{children(data, reload)}</>
}
