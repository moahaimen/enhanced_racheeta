import type { City, Governorate, Paginated } from './providers.types'

export type CompanyVerificationStatus = 'UNVERIFIED' | 'PENDING' | 'VERIFIED' | 'REJECTED' | 'SUSPENDED'

export interface ProductCategory {
  id: string
  slug: string
  name_ar: string
  name_en: string
  parent_id: string | null
  sort_order: number
  /** Backend-derived: active category with an active audience rule. UI guidance only — publication is decided server-side. */
  can_publish: boolean
}

export interface CompanySummary {
  id: string
  name: string
  governorate: Governorate
  city: City | null
  website: string
  public_email: string
  phone: string
}

export interface MedicalCompany {
  id: string
  name: string
  description: string
  phone: string
  public_email: string
  website: string
  governorate: Governorate
  city: City | null
  address: string
  verification_status: CompanyVerificationStatus
  verification_note: string
  verification_requested_at: string | null
  verification_changed_at: string | null
  verified_at: string | null
  /** Backend-computed: verified company with an active account. */
  can_publish: boolean
  /** Name, location and website are frozen while verification is pending or granted (ADR-045). */
  identity_locked: boolean
  created_at: string
  updated_at: string
}

export interface CompanyWrite {
  name?: string
  description?: string
  phone?: string
  public_email?: string
  website?: string
  governorate?: string
  city?: string | null
  address?: string
}

export interface CompanyDashboard {
  verification_status: CompanyVerificationStatus
  can_publish: boolean
  products_total: number
  products_active: number
  products_inactive: number
  /** Active products a matching provider can currently see (backend-computed). */
  products_exposable: number
}

export interface MarketplaceProduct {
  id: string
  title: string
  description: string
  brand: string
  model_name: string
  /** Null = price on request. */
  price: string | null
  currency: string
  category: ProductCategory
  company: CompanySummary
  created_at: string
  updated_at: string
}

export interface CompanyProduct {
  id: string
  title: string
  description: string
  brand: string
  model_name: string
  price: string | null
  currency: string
  category: ProductCategory
  is_active: boolean
  /** B2B = professionals only; B2C/BOTH also list it in the public store (server-checked). */
  sale_channel?: SaleChannel
  /** Restricted / prescription items are B2B-only (database constraint). */
  is_restricted?: boolean
  /** null = stock not tracked (B2B); consumer listings need a figure. */
  stock_quantity?: number | null
  created_at: string
  updated_at: string
}

export type SaleChannel = 'B2B' | 'B2C' | 'BOTH'

/** The only targeting input a company has is the category; audiences are backend rules. */
export interface ProductWrite {
  category?: string
  title?: string
  description?: string
  brand?: string
  model_name?: string
  price?: string | null
  currency?: string
  sale_channel?: SaleChannel
  is_restricted?: boolean
  stock_quantity?: number | null
}

export type PaginatedMarketplaceProducts = Paginated<MarketplaceProduct>
export type PaginatedCompanyProducts = Paginated<CompanyProduct>
