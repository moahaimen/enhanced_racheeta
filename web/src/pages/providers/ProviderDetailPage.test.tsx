import userEvent from '@testing-library/user-event'
import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as providersApi from '../../api/endpoints/providers'
import * as reservationsApi from '../../api/endpoints/reservations'
import * as reviewsApi from '../../api/endpoints/reviews'
import * as offersApi from '../../api/endpoints/offers'
import { tokenStore } from '../../api/tokens'
import { makePublic } from '../../test/providerFixtures'
import { deferred, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/providers')
vi.mock('../../api/endpoints/reservations')
vi.mock('../../api/endpoints/reviews')
vi.mock('../../api/endpoints/offers')
vi.mock('../../api/endpoints/reference')

function makeOffer(id: string, title: string) {
  return {
    id,
    service_title_snapshot: 'Consultation',
    title,
    description: 'Limited',
    original_price_snapshot: '25000.00',
    offer_price: '20000.00',
    currency_snapshot: 'IQD',
    starts_at: '2026-09-28T00:00:00Z',
    ends_at: '2099-10-01T00:00:00Z',
  }
}

describe('ProviderDetailPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
    vi.mocked(reservationsApi.listAvailability).mockResolvedValue([])
    vi.mocked(reviewsApi.listPublicReviews).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    vi.mocked(offersApi.listPublicOffers).mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
  })

  it('shows loading then only real API data', async () => {
    const pending = deferred<ReturnType<typeof makePublic>>()
    vi.mocked(providersApi.getProvider).mockReturnValue(pending.promise)
    renderApp('/providers/p-1')
    expect(screen.getByTestId('async-loading')).toBeInTheDocument()
    pending.resolve(makePublic())
    expect(await screen.findByRole('heading', { name: 'Dr Example' })).toBeInTheDocument()
    expect(providersApi.getProvider).toHaveBeenCalledWith('p-1', expect.anything())
    expect(screen.getByText('About text')).toBeInTheDocument()
    expect(screen.getByText('Consultation')).toBeInTheDocument()
    expect(screen.getAllByText(/\+9647700000000/).length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'City Hospital' })).toHaveAttribute('href', '/providers/p-h')
    expect(await screen.findByText(/لا توجد تقييمات|no reviews yet/i)).toBeInTheDocument()
  })

  it('shows the empty services message', async () => {
    vi.mocked(providersApi.getProvider).mockResolvedValue(makePublic({ services: [], related_providers: [] }))
    renderApp('/providers/p-1')
    expect(await screen.findByText(/لم يُدرج مقدّم الخدمة خدمات|has not listed services/i)).toBeInTheDocument()
  })

  it('shows a not-found message for 404', async () => {
    vi.mocked(providersApi.getProvider).mockRejectedValue(new ApiError(404, 'not_found', 'nope'))
    renderApp('/providers/missing')
    const error = await screen.findByTestId('async-error')
    expect(error).toHaveTextContent(/غير موجود|does not exist/i)
  })

  it('shows rating summary, public offer and review', async () => {
    vi.mocked(providersApi.getProvider).mockResolvedValue(
      makePublic({ average_rating: 4.5, review_count: 2 }),
    )
    vi.mocked(offersApi.listPublicOffers).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [makeOffer('offer-1', 'September offer')],
    })
    vi.mocked(reviewsApi.listPublicReviews).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 'review-1',
          provider_name_snapshot: 'Dr Example',
          service_title_snapshot: 'Consultation',
          rating: 5,
          comment: 'Excellent care',
          created_at: '2026-09-20T00:00:00Z',
        },
      ],
    })

    renderApp('/providers/p-1')

    expect(await screen.findByText(/★ 4\.5/)).toBeInTheDocument()
    expect(await screen.findByText('September offer')).toBeInTheDocument()
    expect(await screen.findByText('Excellent care')).toBeInTheDocument()
  })

  describe('public offers pagination', () => {
    it('renders the first page and loads the next one on demand', async () => {
      vi.mocked(providersApi.getProvider).mockResolvedValue(makePublic())
      vi.mocked(offersApi.listPublicOffers).mockImplementation(async (_id, page = 1) =>
        page === 1
          ? { count: 21, next: 'p2', previous: null, results: Array.from({ length: 20 }, (_, i) => makeOffer(`o-${i}`, `Offer ${i}`)) }
          : { count: 21, next: null, previous: 'p1', results: [makeOffer('o-20', 'Offer 20')] },
      )
      renderApp('/providers/p-1')
      expect(await screen.findByText('Offer 0')).toBeInTheDocument()
      expect(screen.getByText('Offer 19')).toBeInTheDocument()
      expect(screen.queryByText('Offer 20')).toBeNull()
      expect(offersApi.listPublicOffers).toHaveBeenCalledWith('p-1', 1, expect.anything())
      // the offers pagination comes before the reviews pagination in the page
      const next = screen.getAllByRole('button', { name: /التالي|next/i })[0]!
      await userEvent.click(next)
      expect(await screen.findByText('Offer 20')).toBeInTheDocument()
      expect(offersApi.listPublicOffers).toHaveBeenCalledWith('p-1', 2, expect.anything())
      expect(screen.queryByText('Offer 0')).toBeNull()
    })

    it('shows the empty state for a paginated empty response and the error state on failure', async () => {
      vi.mocked(providersApi.getProvider).mockResolvedValue(makePublic())
      renderApp('/providers/p-1')
      expect(await screen.findByText(/لا توجد عروض|no offers/i)).toBeInTheDocument()
      vi.mocked(offersApi.listPublicOffers).mockRejectedValue(new Error('boom'))
      renderApp('/providers/p-1')
      expect((await screen.findAllByRole('alert')).length).toBeGreaterThan(0)
    })
  })
})
