import { screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../api/endpoints/auth'
import * as providersApi from '../api/endpoints/providers'
import * as referenceApi from '../api/endpoints/reference'
import { tokenStore } from '../api/tokens'
import { baghdad } from '../test/providerFixtures'
import { makeAccount, renderApp } from '../test/renderApp'

vi.mock('../api/endpoints/auth')
vi.mock('../api/endpoints/providers')
vi.mock('../api/endpoints/reference')

describe('HomePage provider call-to-action', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad])
    vi.mocked(providersApi.listProviders).mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
  })

  it('sends an anonymous visitor to registration', async () => {
    renderApp('/')
    const cta = await screen.findByTestId('provider-cta')
    expect(within(cta).getByRole('link', { name: /ابدأ كمقدّم خدمة|start as a provider/i })).toHaveAttribute('href', '/register')
  })

  it('sends an authenticated provider to the provider workspace', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PROVIDER' }))
    renderApp('/')
    const cta = await screen.findByTestId('provider-cta')
    await waitFor(() =>
      expect(within(cta).getByRole('link', { name: /ملفي المهني|my provider profile/i })).toHaveAttribute('href', '/provider/profile'),
    )
  })

  it('shows no registration link to an authenticated non-provider', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PATIENT' }))
    renderApp('/')
    const cta = await screen.findByTestId('provider-cta')
    await waitFor(() => expect(within(cta).getByText(/ليس حساب مقدّم خدمة|not a provider account/i)).toBeInTheDocument())
    expect(within(cta).queryByRole('link')).toBeNull()
    expect(screen.queryByRole('link', { name: /أنشئ حسابك|create your account/i })).toBeNull()
  })
})
