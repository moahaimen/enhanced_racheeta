/** Workspaces, store, quotes, preferences and promotions (docs/api/openapi.yaml). */
import type { Paginated } from './providers.types'
import type { PropertyListing } from './realEstate.types'

export type WorkspaceKind =
  | 'patient'
  | 'practitioner'
  | 'facility'
  | 'company'
  | 'property'
  | 'employer'
  | 'job_seeker'
  | 'admin'
export type OrgRole = 'OWNER' | 'MANAGER' | 'STAFF' | 'VIEWER'

export interface Workspace {
  id: string
  /** The organization's own id (facility/company workspaces), else null. */
  org_id: string | null
  /** Staff workspace (reservations / orders / team) when the role can use one. */
  team_path: string | null
  kind: WorkspaceKind
  subtype: string
  title: string
  role: string | null
  path: string
  verification_status: string
  modules: string[]
  capabilities: string[]
}

export interface OrgSummary {
  id: string
  name: string
  role: OrgRole
  capabilities: string[]
  counts: Record<string, number>
  provider_type?: string
  business_type?: string
}

export interface OrgMember {
  id: string
  email: string
  full_name: string
  role: OrgRole
  status: 'ACTIVE' | 'ENDED'
  created_at: string
  ended_at: string | null
}

export interface StoreCategory {
  id: string
  slug: string
  name_ar: string
  name_en: string
}

export interface StoreProduct {
  id: string
  title: string
  description: string
  brand: string
  model_name: string
  price: string
  currency: string
  in_stock: boolean
  category: StoreCategory
  company: { id: string; name: string; business_type?: string }
}

export type OrderStatus = 'PLACED' | 'CONFIRMED' | 'SHIPPED' | 'DELIVERED' | 'CANCELLED'
export type StorePaymentMethod = 'CASH_ON_DELIVERY' | 'MANUAL_TRANSFER'
export type StorePaymentStatus = 'UNPAID' | 'PAID' | 'REFUND_DUE'

export interface OrderItem {
  id: string
  product_id: string
  title_snapshot: string
  unit_price: string
  quantity: number
  line_total: string
}

export interface Order {
  id: string
  number: string
  status: OrderStatus
  payment_method: StorePaymentMethod
  payment_status: StorePaymentStatus
  total: string
  currency: string
  merchant: { id: string; name: string }
  buyer_name: string
  delivery_governorate: { id: string; name_ar: string; name_en: string }
  delivery_city: { id: string; name_ar: string; name_en: string } | null
  delivery_address: string
  contact_phone: string
  note: string
  items: OrderItem[]
  transitions: { from_status: string; to_status: string; reason: string; created_at: string }[]
  created_at: string
  status_changed_at: string | null
}

export interface CheckoutRequest {
  items: { product: string; quantity: number }[]
  payment_method: StorePaymentMethod
  governorate: string
  city?: string | null
  address: string
  phone: string
  note?: string
}

export type QuoteStatus = 'REQUESTED' | 'QUOTED' | 'ACCEPTED' | 'DECLINED' | 'WITHDRAWN'

export interface Quote {
  id: string
  status: QuoteStatus
  quantity: number
  message: string
  product: { id: string; title: string }
  company: { id: string; name: string }
  requester: { id: string; display_name: string; provider_type: string }
  quoted_unit_price: string | null
  quoted_currency: string
  quoted_note: string
  quoted_at: string | null
  closed_at: string | null
  created_at: string
}

export interface MarketingPreferences {
  show_sponsored_products: boolean
  real_estate_promotions: boolean
  job_alerts: boolean
  offers_and_news: boolean
  channel_in_app: boolean
  channel_email: boolean
  channel_push: boolean
}

export type PromotionStatus = 'REQUESTED' | 'ACTIVE' | 'REJECTED' | 'ENDED'

export interface ListingPromotion {
  id: string
  listing: { id: string; title: string }
  target_provider_types: string[]
  days: number
  status: PromotionStatus
  starts_at: string | null
  ends_at: string | null
  reject_reason: string
  created_at: string
}

export interface PromotedListing {
  promotion_id: string
  sponsored: true
  listing: PropertyListing
  ends_at: string
}

export interface ProfessionGroup {
  group: 'HEALTHCARE' | 'HEALTH_BUSINESS' | 'TECHNOLOGY' | 'BUSINESS'
  professions: string[]
}

export type PaginatedOrders = Paginated<Order>
export type PaginatedQuotes = Paginated<Quote>
export type PaginatedStoreProducts = Paginated<StoreProduct>
export type PaginatedPromotions = Paginated<ListingPromotion>
export type PaginatedPromotedListings = Paginated<PromotedListing>
