import { useCallback, useEffect, useRef, useState, type DependencyList } from 'react'

import { ApiError } from '../api/client'

export function toErrorMessage(error: unknown, fallback = 'An unexpected error occurred.'): string {
  if (error instanceof ApiError) return error.message
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
    async (...args: Args): Promise<Result | undefined> => {
      if (pendingRef.current) return undefined
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
