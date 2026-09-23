/** Provider domain types. Mirror docs/api/openapi.yaml. */

export type ProviderType =
  | 'DOCTOR'
  | 'NURSE'
  | 'THERAPIST'
  | 'HOSPITAL'
  | 'MEDICAL_CENTER'
  | 'PHARMACY'
  | 'LABORATORY'
  | 'BEAUTY_CENTER'

export type ProviderKind = 'PRACTITIONER' | 'FACILITY'

export const PROVIDER_TYPES: ProviderType[] = [
  'DOCTOR',
  'NURSE',
  'THERAPIST',
  'HOSPITAL',
  'MEDICAL_CENTER',
  'PHARMACY',
  'LABORATORY',
  'BEAUTY_CENTER',
]

export type VerificationStatus = 'UNVERIFIED' | 'PENDING' | 'VERIFIED' | 'REJECTED' | 'SUSPENDED'
export type MembershipStatus = 'PENDING' | 'ACTIVE' | 'REJECTED' | 'ENDED'
export type MembershipSide = 'PRACTITIONER' | 'FACILITY'

export interface Country {
  id: string
  code: string
  name_ar: string
  name_en: string
}

export interface Governorate {
  id: string
  country: string
  slug: string
  name_ar: string
  name_en: string
}

export interface City {
  id: string
  governorate: string
  slug: string
  name_ar: string
  name_en: string
}

export interface Specialty {
  id: string
  slug: string
  name_ar: string
  name_en: string
  parent: string | null
}

export interface ProviderCard {
  id: string
  provider_type: ProviderType
  kind: ProviderKind
  display_name: string
  governorate: Governorate
  city: City | null
  specialties: Specialty[]
  image_url: string
}

export interface PublicService {
  id: string
  title: string
  description: string
  specialty: Specialty | null
  price: string
  currency: string
  duration_minutes: number | null
}

export interface RelatedProvider {
  id: string
  provider_type: ProviderType
  kind: ProviderKind
  display_name: string
  image_url: string
}

export interface ProviderPublic extends ProviderCard {
  about: string
  phone: string
  public_email: string
  website: string
  address: string
  latitude: string | null
  longitude: string | null
  services: PublicService[]
  related_providers: RelatedProvider[]
  verified_at: string | null
}

export interface ProviderOwner extends ProviderCard {
  can_change_type: boolean
  about: string
  phone: string
  public_email: string
  website: string
  address: string
  latitude: string | null
  longitude: string | null
  is_visible: boolean
  verification_status: VerificationStatus
  verification_note: string
  verification_requested_at: string | null
  verification_changed_at: string | null
  verified_at: string | null
  created_at: string
  updated_at: string
}

export interface ProviderWrite {
  provider_type?: ProviderType
  display_name?: string
  about?: string
  phone?: string
  public_email?: string
  website?: string
  governorate?: string
  city?: string | null
  address?: string
  latitude?: string | null
  longitude?: string | null
  image_url?: string
  specialty_ids?: string[]
  is_visible?: boolean
}

export interface ServiceOffering {
  id: string
  title: string
  description: string
  specialty: string | null
  price: string
  currency: string
  duration_minutes: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ServiceWrite {
  title?: string
  description?: string
  specialty?: string | null
  price?: string
  currency?: string
  duration_minutes?: number | null
  is_active?: boolean
}

export interface Membership {
  id: string
  practitioner: RelatedProvider
  facility: RelatedProvider
  status: MembershipStatus
  initiated_by: MembershipSide
  role_title: string
  my_side: MembershipSide | null
  can_accept: boolean
  responded_at: string | null
  joined_at: string | null
  ended_at: string | null
  created_at: string
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface ProviderListParams {
  type?: ProviderType | ''
  kind?: ProviderKind | ''
  specialty?: string
  governorate?: string
  city?: string
  search?: string
  ordering?: string
  page?: number
  page_size?: number
}
