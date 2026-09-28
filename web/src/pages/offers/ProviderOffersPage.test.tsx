import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../../api/endpoints/auth'
import * as offersApi from '../../api/endpoints/offers'
import * as providersApi from '../../api/endpoints/providers'
import { tokenStore } from '../../api/tokens'
import type { ProviderOffer, ServiceOffering } from '../../api'
import { makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/offers')
vi.mock('../../api/endpoints/providers')

const service: ServiceOffering = {
  id: '11111111-1111-4111-8111-111111111111',
  title: 'Consultation',
  description: '',
  specialty: null,
  price: '25000.00',
  currency: 'IQD',
  duration_minutes: 30,
  is_active: true,
  created_at: '2026-09-28T00:00:00Z',
  updated_at: '2026-09-28T00:00:00Z',
}

const offer: ProviderOffer = {
  id: '22222222-2222-4222-8222-222222222222',
  service_id: service.id,
  service_title_snapshot: service.title,
  title: 'Consultation offer',
  description: 'Limited',
  original_price_snapshot: '25000.00',
  offer_price: '20000.00',
  currency_snapshot: 'IQD',
  starts_at: '2026-09-28T00:00:00Z',
  ends_at: '2099-10-01T00:00:00Z',
  is_active: true,
  created_at: '2026-09-28T00:00:00Z',
  updated_at: '2026-09-28T00:00:00Z',
}

describe('ProviderOffersPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PROVIDER' }))
    vi.mocked(providersApi.listMyServices).mockResolvedValue([service])
    vi.mocked(offersApi.listProviderOffers).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [offer],
    })
  })

  it('shows own offers and can deactivate one', async () => {
    vi.mocked(offersApi.updateProviderOffer).mockResolvedValue({ ...offer, is_active: false })

    renderApp('/provider/offers')

    expect(await screen.findByText('Consultation offer')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /إيقاف العرض|deactivate offer/i }))

    await waitFor(() =>
      expect(offersApi.updateProviderOffer).toHaveBeenCalledWith(offer.id, { is_active: false }),
    )
  })
})
