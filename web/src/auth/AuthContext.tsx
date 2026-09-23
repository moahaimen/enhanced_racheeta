/**
 * The single web session layer. Pages never touch tokens or /me directly;
 * they use `useAuth()`.
 *
 * - status: 'restoring' while a stored session is being re-validated against
 *   GET /api/v1/me on start-up; then 'anonymous' or 'authenticated'.
 * - account: always what the backend last returned for /me.
 * - The token store handles the access/refresh lifecycle (see api/client.ts);
 *   this layer subscribes to it so a failed refresh anywhere logs the UI out.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { ApiError, auth as authApi, tokenStore } from '../api'
import type { Account, LoginRequest, RegisterRequest, UpdateMeRequest } from '../api'
import { AuthContext, type AuthContextValue, type AuthStatus } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>(() =>
    tokenStore.isAuthenticated() ? 'restoring' : 'anonymous',
  )
  const [account, setAccount] = useState<Account | null>(null)
  const [restoreError, setRestoreError] = useState<unknown>(null)
  const statusRef = useRef(status)
  statusRef.current = status

  const becomeAuthenticated = useCallback((next: Account) => {
    setAccount(next)
    setRestoreError(null)
    setStatus('authenticated')
  }, [])

  const becomeAnonymous = useCallback(() => {
    setAccount(null)
    setStatus('anonymous')
  }, [])

  // Session restoration on start-up.
  useEffect(() => {
    if (!tokenStore.isAuthenticated()) return
    let active = true
    authApi
      .getMe()
      .then((me) => {
        if (active) becomeAuthenticated(me)
      })
      .catch((error: unknown) => {
        if (!active) return
        if (error instanceof ApiError && error.status === 401) {
          tokenStore.clear()
          becomeAnonymous()
        } else {
          // Keep the tokens: a network blip must not log the user out.
          setRestoreError(error)
          becomeAnonymous()
        }
      })
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // A failed refresh inside any API call clears the store; mirror it here.
  useEffect(
    () =>
      tokenStore.subscribe((authenticated) => {
        if (!authenticated && statusRef.current === 'authenticated') becomeAnonymous()
      }),
    [becomeAnonymous],
  )

  const login = useCallback(
    async (payload: LoginRequest) => {
      await authApi.login(payload)
      const me = await authApi.getMe()
      becomeAuthenticated(me)
      return me
    },
    [becomeAuthenticated],
  )

  const register = useCallback(
    async (payload: RegisterRequest) => {
      const result = await authApi.register(payload)
      becomeAuthenticated(result.account)
      return result.account
    },
    [becomeAuthenticated],
  )

  const logout = useCallback(async () => {
    // Local session is cleared first; the backend call revokes the refresh
    // token and tolerates "already invalid" (see api/endpoints/auth.ts).
    await authApi.logout()
    becomeAnonymous()
  }, [becomeAnonymous])

  const refreshAccount = useCallback(async () => {
    const me = await authApi.getMe()
    becomeAuthenticated(me)
    return me
  }, [becomeAuthenticated])

  const updateAccount = useCallback(
    async (payload: UpdateMeRequest) => {
      const me = await authApi.updateMe(payload)
      becomeAuthenticated(me)
      return me
    },
    [becomeAuthenticated],
  )

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      account,
      restoreError,
      login,
      register,
      logout,
      refreshAccount,
      updateAccount,
    }),
    [status, account, restoreError, login, register, logout, refreshAccount, updateAccount],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
