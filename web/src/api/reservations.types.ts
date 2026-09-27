import type { Paginated, PublicService, RelatedProvider } from './providers.types'

export type ReservationStatus =
  | 'PENDING'
  | 'CONFIRMED'
  | 'COMPLETED'
  | 'REJECTED'
  | 'CANCELLED'
  | 'NO_SHOW'

export interface AvailabilitySlot {
  id: string
  provider: RelatedProvider
  service: PublicService
  starts_at: string
  ends_at: string
  is_active: boolean
  created_at: string
}

export interface ReservationTransition {
  from_status: ReservationStatus | ''
  to_status: ReservationStatus
  reason: string
  created_at: string
}

export interface ReservationPatient {
  id: string
  provider_id: string | null
  provider_name_snapshot: string
  service_id: string | null
  service_title_snapshot: string
  availability_slot_id: string | null
  price_snapshot: string
  currency_snapshot: string
  duration_minutes_snapshot: number
  starts_at: string
  ends_at: string
  status: ReservationStatus
  status_changed_at: string
  patient_note: string
  transitions: ReservationTransition[]
  created_at: string
}

export interface ReservationProvider extends ReservationPatient {
  patient: {
    id: string
    full_name: string
  }
}

export type PaginatedAvailability = Paginated<AvailabilitySlot>
export type PaginatedPatientReservations = Paginated<ReservationPatient>
export type PaginatedProviderReservations = Paginated<ReservationProvider>
