import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../api/endpoints/auth'
import { tokenStore } from '../api/tokens'
import { deferred, makeAccount, renderApp } from '../test/renderApp'

vi.mock('../api/endpoints/auth')

describe('route guards', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
  })

  it('redirects anonymous visitors from /profile to /login', async () => {
    const { router } = renderApp('/profile')
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.state).toEqual({ from: '/profile' })
  })

  it('shows a loading state while the session is being restored, then renders', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    const me = deferred<ReturnType<typeof makeAccount>>()
    vi.mocked(authApi.getMe).mockReturnValue(me.promise)

    const { router } = renderApp('/profile')
    expect(screen.getByTestId('session-restoring')).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeInTheDocument()

    me.resolve(makeAccount())
    await waitFor(() => expect(router.state.location.pathname).toBe('/profile'))
    expect(await screen.findByRole('heading', { name: /حسابي|my account/i })).toBeInTheDocument()
  })

  it('sends a stored session with a dead token to /login', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    const { ApiError } = await import('../api/client')
    vi.mocked(authApi.getMe).mockRejectedValue(new ApiError(401, 'token_not_valid', 'expired'))
    const { router } = renderApp('/profile')
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(tokenStore.isAuthenticated()).toBe(false)
  })

  it('keeps an authenticated user away from /login', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount())
    const { router } = renderApp('/login')
    await waitFor(() => expect(router.state.location.pathname).toBe('/profile'))
  })

  it('renders the not-found page for unknown routes', async () => {
    renderApp('/definitely/not/here')
    expect(await screen.findByRole('alert')).toHaveTextContent(/غير موجودة|not found/i)
  })
})
