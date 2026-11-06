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
  business_type?: string
  /** Verified AND the store is active: products are offered and can be bought. */
  can_sell?: boolean
  /** A pharmacy store is linked to the pharmacy's provider profile (it stays a provider). */
  facility_id?: string | null
  store_status?: StoreStatus
  store_status_changed_at?: string | null
  required_documents?: SellerDocumentKind[]
  missing_documents?: SellerDocumentKind[]
  tax_mode?: TaxMode
  tax_rate?: string
  tax_label?: string
  tax_registration_number?: string
  default_shipping_fee?: string | null
  free_shipping_over?: string | null
  created_at: string
  updated_at: string
}

export type StoreStatus = 'INACTIVE' | 'ACTIVE' | 'PAUSED'
export type TaxMode = 'NONE' | 'INCLUSIVE' | 'EXCLUSIVE'
export type SellerDocumentKind =
  | 'COMMERCIAL_REGISTRATION'
  | 'PHARMACY_LICENSE'
  | 'MOH_IMPORT_LICENSE'
  | 'SCIENTIFIC_OFFICE_LICENSE'
  | 'DEVICE_REGISTRATION'
  | 'OWNER_ID'
  | 'OTHER'
export type SellerDocumentStatus = 'PENDING' | 'APPROVED' | 'REJECTED'

export interface SellerDocument {
  id: string
  kind: SellerDocumentKind
  original_name: string
  content_type: string
  size: number
  sha256: string
  reference_number: string
  expires_on: string | null
  status: SellerDocumentStatus
  review_note: string
  reviewed_at: string | null
  created_at: string
  file_url: string
  /** Administrator view only. */
  company_id?: string
  company_name?: string
  business_type?: string
}

export interface ShippingRate {
  id: string
  governorate: Governorate
  fee: string
  min_days: number
  max_days: number
  is_active: boolean
}

export interface StoreSettings {
  tax_mode?: TaxMode
  tax_rate?: string
  tax_label?: string
  tax_registration_number?: string
  default_shipping_fee?: string | null
  free_shipping_over?: string | null
}

export interface ProductPhoto {
  id: string
  url: string
  width: number
  height: number
  alt_text: string
  sort_order: number
}

/** A variant as its seller manages it (its own SKU, price and stock). */
export interface OwnerVariant {
  id: string
  sku: string
  label: string
  price: string | null
  stock_quantity: number | null
  stock_reserved: number
  available: number | null
  reorder_threshold: number | null
  is_active: boolean
  sort_order: number
}

/** What a buyer sees of a variant (no stock counts). */
export interface PublicVariant {
  id: string
  sku: string
  label: string
  price: string | null
  in_stock: boolean
  low_stock: boolean
}

export interface VariantWrite {
  sku?: string
  label?: string
  price?: string | null
  stock_quantity?: number | null
  reorder_threshold?: number | null
  is_active?: boolean
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
  /** Product photo; empty = none (the UI shows a neutral placeholder). */
  image_url?: string
  images?: ProductPhoto[]
  variants?: PublicVariant[]
  /** UI hint: a priced product verified professionals may buy without a quotation. */
  can_buy_directly?: boolean
  sku?: string
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
  image_url?: string
  category: ProductCategory
  is_active: boolean
  /** B2B = professionals only; B2C/BOTH also list it in the public store (server-checked). */
  sale_channel?: SaleChannel
  /** Restricted / prescription items are B2B-only (database constraint). */
  is_restricted?: boolean
  /** null = stock not tracked (B2B), or stock lives on the variants. */
  stock_quantity?: number | null
  stock_reserved?: number
  sku?: string
  images?: ProductPhoto[]
  variants?: OwnerVariant[]
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
  image_url?: string
  sku?: string
}

export type PaginatedMarketplaceProducts = Paginated<MarketplaceProduct>
export type PaginatedCompanyProducts = Paginated<CompanyProduct>
