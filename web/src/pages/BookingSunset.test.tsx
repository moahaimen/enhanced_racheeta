/**
 * Reservations sunset (backend RESERVATIONS_ENABLED, served by GET /api/v1/platform/features):
 * with booking OFF no public or account surface invites anyone to book, and the history pages stay
 * reachable under a "reservation history" label. With booking ON the previous UI is unchanged.
 */
import { screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../api/endpoints/auth'
import * as providersApi from '../api/endpoints/providers'
import * as referenceApi from '../api/endpoints/reference'
import * as reservationsApi from '../api/endpoints/reservations'
import { tokenStore } from '../api/tokens'
import { setBookingEnabled } from '../test/features'
import { mockHomeData } from '../test/homeMocks'
import { baghdad, makeCard } from '../test/providerFixtures'
import { makeAccount, renderApp } from '../test/renderApp'

vi.mock('../api/endpoints/auth')
vi.mock('../api/endpoints/providers')
vi.mock('../api/endpoints/reference')
vi.mock('../api/endpoints/jobs')
vi.mock('../api/endpoints/realEstate')
vi.mock('../api/endpoints/marketplace')
vi.mock('../api/endpoints/reservations')

const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results })
/** "Book now" chips: the label sits next to an icon, so match on the element's whole text. */
const bookChips = () =>
  Array.from(document.querySelectorAll('span')).filter((el) => el.textContent?.trim() === 'احجز الآن')

beforeEach(() => {
  vi.resetAllMocks()
  tokenStore.clear()
  mockHomeData()
  vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad])
  vi.mocked(providersApi.listProviders).mockResolvedValue(page([makeCard()]))
})

describe('home page and footer', () => {
  it('OFF: no "book" wording and no footer reservations link', async () => {
    setBookingEnabled(false)
    renderApp('/')
    expect(await screen.findByText('ابحث · تواصل · وظّف')).toBeInTheDocument()
    expect(screen.queryByText('ابحث · احجز · تواصل')).toBeNull()
    const footer = screen.getByRole('contentinfo')
    expect(within(footer).queryByRole('link', { name: /^الحجوزات$/ })).toBeNull()
  })

  it('ON: the previous booking wording and footer link are back', async () => {
    renderApp('/')
    expect(await screen.findByText('ابحث · احجز · تواصل')).toBeInTheDocument()
    const footer = screen.getByRole('contentinfo')
    expect(within(footer).getByRole('link', { name: /^الحجوزات$/ })).toBeInTheDocument()
  })

  it('OFF: the providers directory cards carry no booking chip', async () => {
    setBookingEnabled(false)
    renderApp('/providers')
    expect(await screen.findByText('Dr Example')).toBeInTheDocument()
    expect(bookChips()).toHaveLength(0)
  })

  it('ON: the providers directory cards show the booking chip again', async () => {
    renderApp('/providers')
    expect(await screen.findByText('Dr Example')).toBeInTheDocument()
    await waitFor(() => expect(bookChips().length).toBeGreaterThan(0))
  })
})

describe('signed-in navigation', () => {
  it('OFF: a patient reaches the same history page under "reservation history"', async () => {
    setBookingEnabled(false)
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PATIENT' }))
    vi.mocked(reservationsApi.listMyReservations).mockResolvedValue(page([]))
    renderApp('/reservations')
    expect(await screen.findByTestId('booking-off-notice')).toBeInTheDocument()
    const links = await screen.findAllByRole('link', { name: /سجل الحجوزات/, hidden: true })
    expect(links.every((link) => link.getAttribute('href') === '/reservations')).toBe(true)
    expect(screen.queryByRole('link', { name: /^حجوزاتي$/, hidden: true })).toBeNull()
  })
})
