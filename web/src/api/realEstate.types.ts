import type { City, Governorate, Paginated } from './providers.types'

/** Mirrors backend `apps/real_estate/types.py`; the API rejects any other value. */
export const SELLER_TYPES = ['OWNER', 'AGENT'] as const
export type SellerType = (typeof SELLER_TYPES)[number]

export const PROPERTY_TYPES = [
  'CLINIC',
  'APARTMENT_FOR_CLINIC',
  'MEDICAL_BUILDING',
  'PHARMACY_LOCATION',
  'LABORATORY_LOCATION',
  'MEDICAL_CENTER',
  'HOSPITAL_BUILDING',
  'COMMERCIAL_MEDICAL_PROPERTY',
  'MEDICAL_INVESTMENT_LAND',
] as const
export type PropertyType = (typeof PROPERTY_TYPES)[number]

export const TRANSACTION_TYPES = ['SALE', 'RENT'] as const
export type TransactionType = (typeof TRANSACTION_TYPES)[number]

export const SUITABLE_USES = [
  'CLINIC',
  'PHARMACY',
  'LABORATORY',
  'MEDICAL_CENTER',
  'HOSPITAL',
  'GENERAL_MEDICAL_USE',
  'MEDICAL_INVESTMENT',
] as const
export type SuitableUse = (typeof SUITABLE_USES)[number]

export const CONTACT_METHODS = ['PHONE', 'EMAIL', 'BOTH'] as const
export type ContactMethod = (typeof CONTACT_METHODS)[number]

export type PublicationStatus = 'DRAFT' | 'PUBLISHED'

/** Orderings the backend accepts on the public catalogue. */
export const LISTING_ORDERINGS = ['-created_at', 'created_at', 'price', '-price', 'area_sqm', '-area_sqm'] as const
export type ListingOrdering = (typeof LISTING_ORDERINGS)[number]

/** The public face of a seller: never contact data or account identity. */
export interface SellerSummary {
  id: string
  display_name: string
  seller_type: SellerType
}

export interface RealEstateSeller {
  id: string
  seller_type: SellerType
  display_name: string
  about: string
  phone: string
  public_email: string
  created_at: string
  updated_at: string
}

export interface SellerWrite {
  seller_type?: SellerType
  display_name?: string
  about?: string
  phone?: string
  public_email?: string
}

/** A publicly visible listing (list and detail share it). Decimals arrive as strings. */
export interface PropertyListing {
  id: string
  title: string
  description: string
  property_type: PropertyType
  transaction_type: TransactionType
  governorate: Governorate
  city: City | null
  district: string
  latitude: string | null
  longitude: string | null
  area_sqm: string | null
  /** null = price on request. */
  price: string | null
  currency: string
  suitable_uses: SuitableUse[]
  facilities: string
  contact_method: ContactMethod
  /** Only the values the contact method makes public; otherwise null. */
  contact_phone: string | null
  contact_email: string | null
  seller: SellerSummary
  published_at: string | null
  expires_at: string | null
  created_at: string
  updated_at: string
}

/** Owner-only nested geography: carries the CURRENT `is_active` (and, for a city, its current parent). */
export interface OwnerGovernorate extends Governorate {
  is_active: boolean
}

export interface OwnerCity extends City {
  is_active: boolean
}

/** The owner's view of one of their listings, with lifecycle and derived state. */
export interface OwnerListing {
  id: string
  title: string
  description: string
  property_type: PropertyType
  transaction_type: TransactionType
  governorate: OwnerGovernorate
  city: OwnerCity | null
  district: string
  latitude: string | null
  longitude: string | null
  area_sqm: string | null
  price: string | null
  currency: string
  suitable_uses: SuitableUse[]
  facilities: string
  contact_method: ContactMethod
  contact_phone: string
  contact_email: string
  publication_status: PublicationStatus
  published_at: string | null
  expires_at: string | null
  /** Backend-derived: passes the full public exposure rule right now. */
  is_public: boolean
  /** Backend-derived: PUBLISHED and past its expiry. */
  is_expired: boolean
  created_at: string
  updated_at: string
}

/** The only fields an owner may send; lifecycle, ownership and derived state are server-controlled. */
export interface ListingWrite {
  title?: string
  description?: string
  property_type?: PropertyType
  transaction_type?: TransactionType
  governorate?: string
  city?: string | null
  district?: string
  latitude?: string | null
  longitude?: string | null
  area_sqm?: string | null
  price?: string | null
  currency?: string
  facilities?: string
  contact_method?: ContactMethod
  contact_phone?: string
  contact_email?: string
  expires_at?: string | null
  suitable_uses?: SuitableUse[]
}

export interface OwnerDashboard {
  listings_total: number
  listings_draft: number
  listings_published: number
  listings_visible: number
  listings_expired: number
  listings_sale: number
  listings_rent: number
}

/** Public catalogue filters, sent to the backend as query parameters (never applied client-side). */
export interface ListingFilters {
  transaction_type?: TransactionType | ''
  property_type?: PropertyType | ''
  governorate?: string
  city?: string
  suitable_use?: SuitableUse | ''
  min_price?: string
  max_price?: string
  min_area?: string
  max_area?: string
  search?: string
  ordering?: ListingOrdering | ''
  page?: number
}

export type PaginatedListings = Paginated<PropertyListing>
export type PaginatedOwnerListings = Paginated<OwnerListing>
