/** Phase E web: ask the owner from a listing, follow it as the asker, answer/close as the owner. */
import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as realEstateApi from '../../api/endpoints/realEstate'
import { tokenStore } from '../../api/tokens'
import type { AppNotification, ListingInquiry, OwnerInquiry, PropertyListing } from '../../api'
import { baghdad } from '../../test/providerFixtures'
import { makeAccount, renderApp } from '../../test/renderApp'
import { notificationTarget } from '../notifications/target'

configure({ asyncUtilTimeout: 5000 })

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/realEstate')

const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

const listing: PropertyListing = {
  id: 'l-1',
  title: 'Clinic in Karrada',
  description: '',
  property_type: 'CLINIC',
  transaction_type: 'RENT',
  governorate: baghdad,
  city: null,
  district: 'Karrada',
  latitude: null,
  longitude: null,
  area_sqm: '120.00',
  price: '1500000.00',
  currency: 'IQD',
  suitable_uses: ['CLINIC'],
  facilities: '',
  contact_method: 'PHONE',
  contact_phone: '07700000000',
  contact_email: null,
  seller: { id: 's-1', display_name: 'Al-Noor Realty', seller_type: 'AGENT' },
  published_at: '2026-09-30T00:00:00Z',
  expires_at: '2099-01-01T00:00:00Z',
  created_at: '2026-09-30T00:00:00Z',
  updated_at: '2026-09-30T00:00:00Z',
}

const inquiry: ListingInquiry = {
  id: 'i-1',
  listing_id: 'l-1',
  listing_title_snapshot: 'Clinic in Karrada',
  listing_is_public: true,
  message: 'Is it available next month?',
  share_contact: false,
  status: 'OPEN',
  owner_response: '',
  responded_at: null,
  status_changed_at: '2026-11-01T00:00:00Z',
  created_at: '2026-11-01T00:00:00Z',
}

const ownerInquiry: OwnerInquiry = { ...inquiry, inquirer: { full_name: 'Dr Asker', email: '', phone_number: '' } }

function signIn(role: 'PATIENT' | 'PROVIDER' | 'REAL_ESTATE_SELLER' = 'PROVIDER') {
  tokenStore.set({ access: 'a', refresh: 'r' })
  vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role }))
}

beforeEach(() => {
  vi.resetAllMocks()
  tokenStore.clear()
  vi.mocked(realEstateApi.getListing).mockResolvedValue(listing)
})

describe('ask the owner from a listing', () => {
  it('asks an anonymous visitor to log in and shows no form', async () => {
    renderApp('/real-estate/l-1')
    expect(await screen.findByRole('link', { name: /سجّل الدخول لتسأل المالك|log in to ask/i })).toHaveAttribute('href', '/login')
    expect(screen.queryByTestId('inquiry-form')).toBeNull()
  })

  it('sends the trimmed question and the contact choice, then confirms', async () => {
    signIn()
    vi.mocked(realEstateApi.sendInquiry).mockResolvedValue(inquiry)
    renderApp('/real-estate/l-1')
    const form = await screen.findByTestId('inquiry-form')
    const send = within(form).getByRole('button', { name: /إرسال الاستفسار|send inquiry/i })
    await userEvent.type(within(form).getByLabelText(/سؤالك|your question/i), 'short')
    expect(send).toBeDisabled() // under 10 characters
    await userEvent.type(within(form).getByLabelText(/سؤالك|your question/i), ' question here  ')
    await userEvent.click(within(form).getByLabelText(/شارك رقم هاتفي|share my phone/i))
    await userEvent.click(send)
    await waitFor(() => expect(realEstateApi.sendInquiry).toHaveBeenCalledWith('l-1', 'short question here', true))
    expect(await screen.findByTestId('inquiry-sent')).toBeInTheDocument()
  })

  it('shows the duplicate refusal from the server in the user language', async () => {
    signIn()
    vi.mocked(realEstateApi.sendInquiry).mockRejectedValue(new ApiError(409, 'duplicate_inquiry', 'dup'))
    renderApp('/real-estate/l-1')
    const form = await screen.findByTestId('inquiry-form')
    await userEvent.type(within(form).getByLabelText(/سؤالك|your question/i), 'Is it still available?')
    await userEvent.click(within(form).getByRole('button', { name: /إرسال الاستفسار|send inquiry/i }))
    expect(await within(form).findByText('لديك استفسار مفتوح عن هذا الإعلان.')).toBeInTheDocument()
  })
})

describe('my property inquiries', () => {
  it('shows the answer, links only a public listing and withdraws a live inquiry', async () => {
    signIn('PATIENT')
    const answered = { ...inquiry, status: 'ANSWERED' as const, owner_response: 'Yes, from the 1st.' }
    const gone = { ...inquiry, id: 'i-2', listing_id: 'l-2', listing_title_snapshot: 'Old pharmacy', listing_is_public: false, status: 'CLOSED' as const }
    vi.mocked(realEstateApi.listMyInquiries).mockResolvedValue(page([answered, gone]))
    vi.mocked(realEstateApi.withdrawMyInquiry).mockResolvedValue({ ...answered, status: 'WITHDRAWN' })
    renderApp('/real-estate/inquiries')
    const rows = await screen.findAllByTestId('my-inquiry')
    expect(within(rows[0]!).getByTestId('owner-response')).toHaveTextContent('Yes, from the 1st.')
    expect(within(rows[0]!).getByRole('link', { name: 'Clinic in Karrada' })).toHaveAttribute('href', '/real-estate/l-1')
    expect(within(rows[1]!).queryByRole('link', { name: 'Old pharmacy' })).toBeNull()
    expect(within(rows[1]!).getByText('هذا الإعلان لم يعد منشوراً.')).toBeInTheDocument()
    expect(within(rows[1]!).queryByRole('button', { name: /سحب|withdraw/i })).toBeNull()
    await userEvent.click(within(rows[0]!).getByRole('button', { name: /سحب|withdraw/i }))
    await waitFor(() => expect(realEstateApi.withdrawMyInquiry).toHaveBeenCalledWith('i-1'))
  })
})

describe('owner inbox', () => {
  it('keeps unshared contact details private, answers and closes', async () => {
    signIn('REAL_ESTATE_SELLER')
    vi.mocked(realEstateApi.listOwnerInquiries).mockResolvedValue(page([ownerInquiry]))
    vi.mocked(realEstateApi.respondToInquiry).mockResolvedValue({ ...ownerInquiry, status: 'ANSWERED' })
    vi.mocked(realEstateApi.closeInquiry).mockResolvedValue({ ...ownerInquiry, status: 'CLOSED' })
    renderApp('/real-estate/owner/inquiries')
    const row = await screen.findByTestId('owner-inquiry')
    expect(within(row).getByText(/Dr Asker/)).toBeInTheDocument()
    expect(within(row).queryByTestId('inquirer-contact')).toBeNull()
    await userEvent.type(within(row).getByLabelText(/ردّك|your answer/i), 'Yes, available.')
    await userEvent.click(within(row).getByRole('button', { name: /إرسال الرد|send answer/i }))
    await waitFor(() => expect(realEstateApi.respondToInquiry).toHaveBeenCalledWith('i-1', 'Yes, available.'))
    await userEvent.click(within(row).getByRole('button', { name: /إغلاق الاستفسار|close inquiry/i }))
    await waitFor(() => expect(realEstateApi.closeInquiry).toHaveBeenCalledWith('i-1'))
  })

  it('shows shared contact details and filters by status on the server', async () => {
    signIn('REAL_ESTATE_SELLER')
    vi.mocked(realEstateApi.listOwnerInquiries).mockResolvedValue(
      page([{ ...ownerInquiry, share_contact: true, inquirer: { full_name: 'Dr Asker', email: 'asker@example.com', phone_number: '07701234567' } }]),
    )
    renderApp('/real-estate/owner/inquiries')
    expect(await screen.findByTestId('inquirer-contact')).toHaveTextContent('07701234567')
    await userEvent.selectOptions(screen.getByLabelText(/الحالة|status/i), 'ANSWERED')
    await waitFor(() =>
      expect(realEstateApi.listOwnerInquiries).toHaveBeenLastCalledWith({ status: 'ANSWERED', page: 1 }, expect.anything()),
    )
  })

  it('is closed to accounts that are not property sellers', async () => {
    signIn('PATIENT')
    renderApp('/real-estate/owner/inquiries')
    await waitFor(() => expect(realEstateApi.listOwnerInquiries).not.toHaveBeenCalled())
    expect(screen.queryByTestId('owner-inquiries')).toBeNull()
  })
})

describe('notification links', () => {
  const note = (event_type: AppNotification['event_type']): AppNotification => ({
    id: 'n', category: 'INQUIRY', event_type, title: '', body: '', resource_type: 'INQUIRY',
    resource_id: 'i-1', is_read: false, read_at: null, created_at: '2026-11-01T00:00:00Z',
  })
  it('sends the owner to the inbox and the asker to their own list', () => {
    expect(notificationTarget(note('INQUIRY_RECEIVED'), 'REAL_ESTATE_SELLER')).toBe('/real-estate/owner/inquiries')
    expect(notificationTarget(note('INQUIRY_ANSWERED'), 'PATIENT')).toBe('/real-estate/inquiries')
  })
})
