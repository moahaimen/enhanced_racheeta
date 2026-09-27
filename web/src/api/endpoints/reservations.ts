import { apiRequest } from '../client'
import type {
  AvailabilitySlot,
  PaginatedAvailability,
  PaginatedPatientReservations,
  PaginatedProviderReservations,
  ReservationPatient,
  ReservationProvider,
  ReservationStatus,
} from '../reservations.types'

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '') continue
    search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

export function listAvailability(
  providerId: string,
  params: { service?: string; from?: string; to?: string } = {},
  signal?: AbortSignal,
): Promise<AvailabilitySlot[]> {
  return apiRequest<AvailabilitySlot[]>(
    `/api/v1/providers/${encodeURIComponent(providerId)}/availability${buildQuery(params)}`,
    { auth: false, signal },
  )
}

export function createReservation(availabilitySlot: string, patientNote = ''): Promise<ReservationPatient> {
  return apiRequest<ReservationPatient>('/api/v1/reservations', {
    method: 'POST',
    body: { availability_slot: availabilitySlot, patient_note: patientNote },
  })
}

export function listMyReservations(page = 1, signal?: AbortSignal): Promise<PaginatedPatientReservations> {
  return apiRequest<PaginatedPatientReservations>(
    `/api/v1/reservations/me${buildQuery({ page })}`,
    { signal },
  )
}

export function cancelMyReservation(id: string, reason = ''): Promise<ReservationPatient> {
  return apiRequest<ReservationPatient>(
    `/api/v1/reservations/me/${encodeURIComponent(id)}/cancel`,
    { method: 'POST', body: { reason } },
  )
}

export function listProviderAvailability(page = 1, signal?: AbortSignal): Promise<PaginatedAvailability> {
  return apiRequest<PaginatedAvailability>(
    `/api/v1/reservations/provider/availability${buildQuery({ page })}`,
    { signal },
  )
}

export function createProviderAvailability(service: string, startsAt: string): Promise<AvailabilitySlot> {
  return apiRequest<AvailabilitySlot>('/api/v1/reservations/provider/availability', {
    method: 'POST',
    body: { service, starts_at: startsAt },
  })
}

export function deleteProviderAvailability(id: string): Promise<void> {
  return apiRequest<void>(
    `/api/v1/reservations/provider/availability/${encodeURIComponent(id)}`,
    { method: 'DELETE' },
  )
}

export function listProviderReservations(page = 1, signal?: AbortSignal): Promise<PaginatedProviderReservations> {
  return apiRequest<PaginatedProviderReservations>(
    `/api/v1/reservations/provider${buildQuery({ page })}`,
    { signal },
  )
}

export function transitionProviderReservation(
  id: string,
  status: ReservationStatus,
  reason = '',
): Promise<ReservationProvider> {
  return apiRequest<ReservationProvider>(
    `/api/v1/reservations/provider/${encodeURIComponent(id)}/transition`,
    { method: 'POST', body: { status, reason } },
  )
}
