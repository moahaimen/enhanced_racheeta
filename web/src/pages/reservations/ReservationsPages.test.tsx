import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../../api/endpoints/auth'
import * as providersApi from '../../api/endpoints/providers'
import * as reservationsApi from '../../api/endpoints/reservations'
import { tokenStore } from '../../api/tokens'
import type { AvailabilitySlot, ReservationPatient, ReservationProvider, ServiceOffering } from '../../api'
import { makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/providers')
vi.mock('../../api/endpoints/reservations')

const service: ServiceOffering = {
  id: '11111111-1111-4111-8111-111111111111',
  title: 'Consultation',
  description: '',
  specialty: null,
  price: '25000.00',
  currency: 'IQD',
  duration_minutes: 30,
  is_active: true,
  created_at: '2026-09-27T00:00:00Z',
  updated_at: '2026-09-27T00:00:00Z',
}

const slot: AvailabilitySlot = {
  id: '22222222-2222-4222-8222-222222222222',
  provider: {
    id: '33333333-3333-4333-8333-333333333333',
    provider_type: 'DOCTOR',
    kind: 'PRACTITIONER',
    display_name: 'Dr Booking',
    image_url: '',
  },
  service: {
    id: service.id,
    title: service.title,
    description: '',
    specialty: null,
    price: service.price,
    currency: service.currency,
    duration_minutes: service.duration_minutes,
  },
  starts_at: '2099-10-01T09:00:00Z',
  ends_at: '2099-10-01T09:30:00Z',
  is_active: true,
  created_at: '2026-09-27T00:00:00Z',
}

const patientReservation: ReservationPatient = {
  id: '44444444-4444-4444-8444-444444444444',
  provider_id: slot.provider.id,
  provider_name_snapshot: slot.provider.display_name,
  service_id: service.id,
  service_title_snapshot: service.title,
  availability_slot_id: slot.id,
  price_snapshot: service.price,
  currency_snapshot: service.currency,
  duration_minutes_snapshot: 30,
  starts_at: slot.starts_at,
  ends_at: slot.ends_at,
  status: 'PENDING',
  status_changed_at: '2026-09-27T00:00:00Z',
  patient_note: '',
  transitions: [
    {
      from_status: '',
      to_status: 'PENDING',
      reason: '',
      created_at: '2026-09-27T00:00:00Z',
    },
  ],
  created_at: '2026-09-27T00:00:00Z',
}

const providerReservation: ReservationProvider = {
  ...patientReservation,
  patient: { id: '55555555-5555-4555-8555-555555555555', full_name: 'Patient One' },
}

describe('Reservations pages', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
  })

  it('shows a patient reservation and cancels it', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PATIENT' }))
    vi.mocked(reservationsApi.listMyReservations)
      .mockResolvedValueOnce({ count: 1, next: null, previous: null, results: [patientReservation] })
      .mockResolvedValue({ count: 1, next: null, previous: null, results: [{ ...patientReservation, status: 'CANCELLED' }] })
    vi.mocked(reservationsApi.cancelMyReservation).mockResolvedValue({ ...patientReservation, status: 'CANCELLED' })

    renderApp('/reservations')

    expect(await screen.findByText('Dr Booking')).toBeInTheDocument()
    const cancel = screen.getByRole('button', { name: /إلغاء الحجز|cancel reservation/i })
    await userEvent.click(cancel)
    await waitFor(() => expect(reservationsApi.cancelMyReservation).toHaveBeenCalledWith(patientReservation.id))
  })

  it('lets a provider create availability and manage a pending reservation', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PROVIDER' }))
    vi.mocked(providersApi.listMyServices).mockResolvedValue([service])
    vi.mocked(reservationsApi.listProviderAvailability)
      .mockResolvedValueOnce({ count: 0, next: null, previous: null, results: [] })
      .mockResolvedValue({ count: 1, next: null, previous: null, results: [slot] })
    vi.mocked(reservationsApi.listProviderReservations).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [providerReservation],
    })
    vi.mocked(reservationsApi.createProviderAvailability).mockResolvedValue(slot)
    vi.mocked(reservationsApi.transitionProviderReservation).mockResolvedValue({
      ...providerReservation,
      status: 'CONFIRMED',
    })

    renderApp('/provider/reservations')

    expect(await screen.findByText('Patient One')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText(/الخدمة|service/i), service.id)
    await userEvent.type(screen.getByLabelText(/بداية الموعد|appointment start/i), '2099-10-01T09:00')
    await userEvent.click(screen.getByRole('button', { name: /إضافة موعد متاح|add available time/i }))
    await waitFor(() => expect(reservationsApi.createProviderAvailability).toHaveBeenCalledWith(service.id, expect.stringMatching(/^2099-10-01T/)))

    await userEvent.click(screen.getByRole('button', { name: /^قبول$|^accept$/i }))
    await waitFor(() => expect(reservationsApi.transitionProviderReservation).toHaveBeenCalledWith(providerReservation.id, 'CONFIRMED'))
  })
  it('hides accept for a pending reservation after its appointment has started', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PROVIDER' }))
    vi.mocked(providersApi.listMyServices).mockResolvedValue([service])
    vi.mocked(reservationsApi.listProviderAvailability).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    vi.mocked(reservationsApi.listProviderReservations).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          ...providerReservation,
          starts_at: '2020-01-01T09:00:00Z',
          ends_at: '2020-01-01T09:30:00Z',
          status: 'PENDING',
        },
      ],
    })

    renderApp('/provider/reservations')

    expect(await screen.findByText('Patient One')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^قبول$|^accept$/i })).toBeNull()
    expect(screen.getByRole('button', { name: /^رفض$|^reject$/i })).toBeInTheDocument()
  })

  it('paginates provider availability and received reservations independently', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PROVIDER' }))
    vi.mocked(providersApi.listMyServices).mockResolvedValue([service])
    vi.mocked(reservationsApi.listProviderAvailability).mockImplementation(async (page = 1) => ({
      count: 21,
      next: page === 1 ? 'http://test/api/v1/reservations/provider/availability?page=2' : null,
      previous: page === 2 ? 'http://test/api/v1/reservations/provider/availability?page=1' : null,
      results: [{ ...slot, id: page === 1 ? slot.id : '66666666-6666-4666-8666-666666666666' }],
    }))
    vi.mocked(reservationsApi.listProviderReservations).mockImplementation(async (page = 1) => ({
      count: 21,
      next: page === 1 ? 'http://test/api/v1/reservations/provider?page=2' : null,
      previous: page === 2 ? 'http://test/api/v1/reservations/provider?page=1' : null,
      results: [
        {
          ...providerReservation,
          id: page === 1 ? providerReservation.id : '77777777-7777-4777-8777-777777777777',
        },
      ],
    }))

    renderApp('/provider/reservations')

    expect(await screen.findByText('Patient One')).toBeInTheDocument()
    const nextButtons = screen.getAllByRole('button', { name: /التالي|next/i })
    expect(nextButtons).toHaveLength(2)

    await userEvent.click(nextButtons[0])
    await waitFor(() =>
      expect(reservationsApi.listProviderAvailability).toHaveBeenCalledWith(2, expect.anything()),
    )
    expect(reservationsApi.listProviderReservations).not.toHaveBeenCalledWith(2, expect.anything())

    const updatedNextButtons = screen.getAllByRole('button', { name: /التالي|next/i })
    await userEvent.click(updatedNextButtons[1])
    await waitFor(() =>
      expect(reservationsApi.listProviderReservations).toHaveBeenCalledWith(2, expect.anything()),
    )
  })

})
