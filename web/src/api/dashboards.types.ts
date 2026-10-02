import type { ProviderType, VerificationStatus } from './providers.types'
import type { ReservationStatus } from './reservations.types'

/** Which dashboard a signed-in account can open (decided by the server). */
export type DashboardKey =
  | 'patient'
  | 'doctor'
  | 'facility'
  | 'medical_company'
  | 'real_estate_owner'
  | 'recruiter'
  | 'admin'

export interface DashboardIndex {
  dashboards: DashboardKey[]
}

/** Every status is present (zero-filled) so a missing key never has to be interpreted. */
export type StatusCounts<S extends string> = Record<S, number>

export interface ReservationCounts {
  total: number
  by_status: StatusCounts<ReservationStatus>
  /** PENDING or CONFIRMED reservations that have not started yet. */
  upcoming: number
}

export interface ReservationBrief {
  id: string
  provider_name_snapshot: string
  service_title_snapshot: string
  starts_at: string
  ends_at: string
  status: ReservationStatus
}

export interface ProviderAppointment extends ReservationBrief {
  patient_name: string
}

export interface DashboardUnread {
  notifications: number
  messages: number
}

export interface PatientDashboard {
  reservations: ReservationCounts
  upcoming: ReservationBrief[]
  recent: ReservationBrief[]
  unread: DashboardUnread
}

export interface ReviewSummary {
  /** Null when there are no reviews (never a fabricated 0). */
  average_rating: number | null
  review_count: number
  distribution: Record<'1' | '2' | '3' | '4' | '5', number>
}

export interface OfferSummary {
  total: number
  running_now: number
  scheduled: number
}

export interface DoctorDashboard {
  profile: {
    display_name: string
    provider_type: ProviderType
    verification_status: VerificationStatus
    is_visible: boolean
  }
  reservations: ReservationCounts
  upcoming: ProviderAppointment[]
  reviews: ReviewSummary
  offers: OfferSummary
  unread: DashboardUnread
}

export interface FacilityDashboard extends DoctorDashboard {
  practitioners: {
    active: number
    /** Practitioner requests waiting for the facility's answer. */
    incoming_requests: number
    /** Facility invitations waiting for the practitioner's answer. */
    outgoing_invitations: number
  }
}

export interface MedicalCompanyDashboard {
  verification_status: 'UNVERIFIED' | 'PENDING' | 'VERIFIED' | 'REJECTED' | 'SUSPENDED'
  can_publish: boolean
  products: { total: number; active: number; inactive: number; exposable: number }
  campaigns: {
    total: number
    draft: number
    pending_payment: number
    active: number
    live: number
    ended: number
    rejected: number
    cancelled: number
  }
  payments: StatusCounts<'PENDING' | 'VERIFIED' | 'REJECTED'>
}

export type JobStatusKey =
  | 'DRAFT'
  | 'PENDING_ADMIN_REVIEW'
  | 'PUBLISHED'
  | 'CLOSED'
  | 'EXPIRED'
  | 'REJECTED'
  | 'SUSPENDED'
  | 'ARCHIVED'
export type ApplicationStatusKey =
  | 'SUBMITTED'
  | 'REVIEWING'
  | 'SHORTLISTED'
  | 'INTERVIEW'
  | 'ACCEPTED'
  | 'REJECTED'
  | 'WITHDRAWN'

export interface RecruiterDashboard {
  organization: {
    id: string
    name: string
    verification_status: 'UNVERIFIED' | 'PENDING' | 'VERIFIED' | 'REJECTED' | 'SUSPENDED'
    recruitment_status: string
    can_recruit: boolean
    my_role: string
  }
  jobs: { total: number; by_status: StatusCounts<JobStatusKey>; open_now: number }
  /** Null when applicant aggregates are included; otherwise the reason they are withheld. */
  applications_access: 'organization_not_verified' | 'plan_required' | null
  applications: {
    total: number
    by_status: StatusCounts<ApplicationStatusKey>
    awaiting_review: number
    last_7_days: number
  } | null
  interviews: {
    total: number
    by_status: StatusCounts<'PROPOSED' | 'ACCEPTED' | 'DECLINED' | 'CANCELLED'>
  } | null
  seats: { active_members: number; enabled: boolean; limit: number | null }
}

export interface AdminDashboard {
  accounts: {
    total: number
    active: number
    inactive: number
    by_role: StatusCounts<'PATIENT' | 'PROVIDER' | 'MEDICAL_COMPANY' | 'REAL_ESTATE_SELLER' | 'ADMIN'>
  }
  providers: { by_verification: StatusCounts<VerificationStatus> }
  medical_companies: { by_verification: StatusCounts<VerificationStatus> }
  employers: { by_verification: StatusCounts<VerificationStatus>; recruitment_suspended: number }
  jobs: { by_status: StatusCounts<JobStatusKey> }
  reservations: { by_status: StatusCounts<ReservationStatus> }
  marketplace: { products: { total: number; active: number } }
  real_estate: { listings_by_status: StatusCounts<'DRAFT' | 'PUBLISHED'> }
  advertising: {
    campaigns_by_status: StatusCounts<'DRAFT' | 'PENDING_PAYMENT' | 'ACTIVE' | 'REJECTED' | 'CANCELLED'>
    payments_by_status: StatusCounts<'PENDING' | 'VERIFIED' | 'REJECTED'>
  }
  billing: {
    subscriptions_by_status: StatusCounts<
      'PENDING' | 'ACTIVE' | 'SUSPENDED' | 'CANCELLED' | 'EXPIRED' | 'REJECTED'
    >
  }
  audit: { last_24_hours: number; last_7_days: number }
}
