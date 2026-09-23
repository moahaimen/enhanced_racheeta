/**
 * The single HTTP layer every feature uses. Never call fetch() elsewhere.
 *
 * - Prefixes VITE_API_BASE_URL (empty = same origin, works with the Vite proxy
 *   in development and with Django serving the build in production).
 * - Attaches the Bearer access token.
 * - On 401, refreshes once via /api/v1/auth/refresh and retries; if that fails
 *   the session is cleared.
 * - Converts the backend error envelope into a typed ApiError.
 */
import i18next from 'i18next'

import { tokenStore } from './tokens'
import type { ApiErrorBody, TokenPair } from './types'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, string[]> | undefined

  constructor(status: number, code: string, message: string, details?: Record<string, string[]>) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }

  /** First message for a field, or undefined. Handy for form errors. */
  fieldError(field: string): string | undefined {
    return this.details?.[field]?.[0]
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  /** Attach the access token (default true). */
  auth?: boolean
  signal?: AbortSignal
  /** Internal: prevents infinite refresh loops. */
  _retried?: boolean
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === 'object' &&
    value !== null &&
    'error' in value &&
    typeof (value as ApiErrorBody).error?.code === 'string'
  )
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined
  const text = await response.text()
  if (!text) return undefined
  try {
    return JSON.parse(text) as unknown
  } catch {
    return text
  }
}

let refreshInFlight: Promise<boolean> | null = null

/** Rotate the refresh token. Resolves true when the session is still valid. */
export async function refreshSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    const refresh = tokenStore.getRefresh()
    if (!refresh) return false
    try {
      const tokens = await apiRequest<TokenPair>('/api/v1/auth/refresh', {
        method: 'POST',
        body: { refresh },
        auth: false,
        _retried: true,
      })
      tokenStore.set(tokens)
      return true
    } catch {
      tokenStore.clear()
      return false
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true, signal, _retried = false } = options
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  // Backend validation messages come back in the UI language.
  if (i18next.language) headers['Accept-Language'] = i18next.language
  const access = auth ? tokenStore.getAccess() : null
  if (access) headers.Authorization = `Bearer ${access}`

  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'network_error', 'Could not reach the server.')
  }

  if (response.status === 401 && auth && !_retried && tokenStore.getRefresh()) {
    const ok = await refreshSession()
    if (ok) return apiRequest<T>(path, { ...options, _retried: true })
  }

  const data = await parseBody(response)
  if (!response.ok) {
    if (isErrorBody(data)) {
      throw new ApiError(response.status, data.error.code, data.error.message, data.error.details)
    }
    throw new ApiError(response.status, 'http_error', `Request failed with status ${response.status}.`)
  }
  return data as T
}
