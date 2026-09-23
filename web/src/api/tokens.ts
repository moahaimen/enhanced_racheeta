/**
 * Session token storage.
 *
 * Access token: memory only (short-lived, never persisted).
 * Refresh token: localStorage so a reload keeps the session. This is an
 * accepted Phase 0 trade-off documented in docs/SECURITY.md; an httpOnly
 * cookie flow is a candidate for production hardening.
 */
import type { TokenPair } from './types'

const REFRESH_KEY = 'racheeta.refresh'

type Listener = (authenticated: boolean) => void

let accessToken: string | null = null
const listeners = new Set<Listener>()

function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function safeSet(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    /* ignore: storage unavailable */
  }
}

function notify(): void {
  const authenticated = tokenStore.isAuthenticated()
  listeners.forEach((listener) => listener(authenticated))
}

export const tokenStore = {
  getAccess(): string | null {
    return accessToken
  },
  getRefresh(): string | null {
    return safeGet(REFRESH_KEY)
  },
  set(tokens: TokenPair): void {
    accessToken = tokens.access
    safeSet(REFRESH_KEY, tokens.refresh)
    notify()
  },
  clear(): void {
    accessToken = null
    safeSet(REFRESH_KEY, null)
    notify()
  },
  isAuthenticated(): boolean {
    return accessToken !== null || safeGet(REFRESH_KEY) !== null
  },
  subscribe(listener: Listener): () => void {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
}
