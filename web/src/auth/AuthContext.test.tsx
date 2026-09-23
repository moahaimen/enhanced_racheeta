import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as authApi from '../api/endpoints/auth'
import { tokenStore } from '../api/tokens'
import { AuthProvider } from './AuthContext'
import { useAuth } from './useAuth'
import { makeAccount } from '../test/renderApp'

vi.mock('../api/endpoints/auth')

const wrapper = ({ children }: { children: ReactNode }) => <AuthProvider>{children}</AuthProvider>

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
  })

  it('starts anonymous without stored tokens and never calls /me', () => {
    const { result } = renderHook(() => useAuth(), { wrapper })
    expect(result.current.status).toBe('anonymous')
    expect(authApi.getMe).not.toHaveBeenCalled()
  })

  it('restores a stored session from /me', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ full_name: 'Restored' }))
    const { result } = renderHook(() => useAuth(), { wrapper })
    expect(result.current.status).toBe('restoring')
    await waitFor(() => expect(result.current.status).toBe('authenticated'))
    expect(result.current.account?.full_name).toBe('Restored')
  })

  it('keeps tokens on a network failure during restoration', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockRejectedValue(new ApiError(0, 'network_error', 'offline'))
    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.status).toBe('anonymous'))
    expect(result.current.restoreError).toBeInstanceOf(ApiError)
    expect(tokenStore.getRefresh()).toBe('r')
  })

  it('login fetches /me and becomes authenticated', async () => {
    vi.mocked(authApi.login).mockResolvedValue({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount())
    const { result } = renderHook(() => useAuth(), { wrapper })
    await act(async () => {
      await result.current.login({ email: 'person@example.com', password: 'x' })
    })
    expect(result.current.status).toBe('authenticated')
    expect(result.current.account?.email).toBe('person@example.com')
  })

  it('logout calls the backend and becomes anonymous', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount())
    vi.mocked(authApi.logout).mockResolvedValue(undefined)
    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.status).toBe('authenticated'))
    await act(async () => {
      await result.current.logout()
    })
    expect(authApi.logout).toHaveBeenCalledTimes(1)
    expect(result.current.status).toBe('anonymous')
    expect(result.current.account).toBeNull()
  })

  it('becomes anonymous when the token store is cleared elsewhere (failed refresh)', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount())
    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.status).toBe('authenticated'))
    act(() => tokenStore.clear())
    expect(result.current.status).toBe('anonymous')
  })

  it('updateAccount stores the account returned by PATCH /me', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount())
    vi.mocked(authApi.updateMe).mockResolvedValue(makeAccount({ full_name: 'Renamed' }))
    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.status).toBe('authenticated'))
    await act(async () => {
      await result.current.updateAccount({ full_name: 'Renamed' })
    })
    expect(result.current.account?.full_name).toBe('Renamed')
  })
})
