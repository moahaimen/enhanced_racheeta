import { useCallback, useEffect, useRef, useState, type DependencyList } from 'react'

import i18next from 'i18next'

import { ApiError } from '../api/client'

/** Returned by `useAsyncAction().run` when a call is ignored because one is already pending,
 * so a legitimate `undefined` result (a DELETE, a 204) is never mistaken for a skipped click. */
export const DUPLICATE_CALL = Symbol('duplicate-call')

export function toErrorMessage(error: unknown, fallback = 'An unexpected error occurred.'): string {
  if (error instanceof ApiError) {
    const tr = (key: string) => (i18next.isInitialized ? i18next.t(`apiErrors.${key}`, { defaultValue: '' }) : '')
    if (error.code === 'validation_error') {
      // Field-level typed codes (e.g. contact_information_not_allowed) beat the generic message.
      for (const codes of Object.values(error.codes ?? {})) {
        const translated = codes[0] ? tr(codes[0]) : ''
        if (translated) return translated
      }
      const first = Object.values(error.details ?? {})[0]?.[0]
      return first || error.message
    }
    return tr(error.code) || error.message
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}

/**
 * Wraps a backend mutation. `pending` is true while the promise is running,
 * duplicate runs are ignored, and state updates are skipped after unmount.
 */
export function useAsyncAction<Args extends unknown[], Result>(
  action: (...args: Args) => Promise<Result>,
) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const pendingRef = useRef(false)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const run = useCallback(
    async (...args: Args): Promise<Result | typeof DUPLICATE_CALL> => {
      if (pendingRef.current) return DUPLICATE_CALL
      pendingRef.current = true
      setPending(true)
      setError(null)
      try {
        return await action(...args)
      } catch (err) {
        if (mountedRef.current) setError(err)
        throw err
      } finally {
        pendingRef.current = false
        if (mountedRef.current) setPending(false)
      }
    },
    [action],
  )

  return { run, pending, error }
}

export interface AsyncDataState<T> {
  data: T | undefined
  loading: boolean
  error: unknown
  reload: () => void
}

/**
 * Loads backend data on mount (and whenever `deps` change). Cancels the
 * in-flight request on unmount/re-run via AbortSignal.
 */
export function useAsyncData<T>(
  load: (signal: AbortSignal) => Promise<T>,
  deps: DependencyList = [],
): AsyncDataState<T> {
  const [data, setData] = useState<T | undefined>(undefined)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setLoading(true)
    setError(null)
    load(controller.signal)
      .then((result) => {
        if (active) setData(result)
      })
      .catch((err: unknown) => {
        if (!active) return
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps])

  const reload = useCallback(() => setTick((n) => n + 1), [])
  return { data, loading, error, reload }
}
