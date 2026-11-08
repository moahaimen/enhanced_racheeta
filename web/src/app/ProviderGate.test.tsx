import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as authApi from '../api/endpoints/auth'
import * as marketplaceApi from '../api/endpoints/marketplace'
import * as providersApi from '../api/endpoints/providers'
import * as reservationsApi from '../api/endpoints/reservations'
import { tokenStore } from '../api/tokens'
import { makeOwner } from '../test/providerFixtures'
import { makeAccount, renderApp } from '../test/renderApp'

vi.mock('../api/endpoints/auth')
vi.mock('../api/endpoints/providers')
vi.mock('../api/endpoints/marketplace')
vi.mock('../api/endpoints/reservations')

beforeEach(() => {
  vi.resetAllMocks()
  tokenStore.set({ access: 'a', refresh: 'r' })
  vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PROVIDER', full_name: 'sami' }))
})

describe('provider pages for a new or unverified provider', () => {
  it('a provider without a profile gets a create-profile prompt, never the raw refusal', async () => {
    vi.mocked(providersApi.getMyProvider).mockRejectedValue(new ApiError(404, 'not_found', 'Not found.'))
    for (const path of ['/provider/reservations', '/marketplace', '/quotes']) {
      const { unmount } = renderApp(path)
      expect(await screen.findByTestId('provider-profile-required')).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /إنشاء الملف المهني/ })).toHaveAttribute('href', '/provider/profile')
      expect(screen.queryByText(/Create your provider profile first/)).toBeNull()
      unmount()
    }
    expect(reservationsApi.listProviderReservations).not.toHaveBeenCalled()
    expect(marketplaceApi.listTargetedProducts).not.toHaveBeenCalled()
  })

  it('an unverified provider can manage reservations but sees a verification prompt on the marketplace', async () => {
    vi.mocked(providersApi.getMyProvider).mockResolvedValue(makeOwner({ verification_status: 'PENDING' }))
    renderApp('/marketplace')
    expect(await screen.findByTestId('provider-verification-required')).toBeInTheDocument()
    expect(marketplaceApi.listTargetedProducts).not.toHaveBeenCalled()
  })
})
