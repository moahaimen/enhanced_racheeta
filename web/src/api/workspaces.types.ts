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
  /** The workspace the dashboard opens by default (staff: their organization). */
  is_default?: boolean
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
  /** Category rule shown to buyers (e.g. "use under supervision"). */
  buyer_notice_ar?: string
  buyer_notice_en?: string
  /** Most units of one product per order (null = the general limit). */
  max_order_quantity?: number | null
}

export interface StoreProduct {
  id: string
  title: string
  description: string
  brand: string
  model_name: string
  price: string
  currency: string
  image_url?: string
  in_stock: boolean
  /** "Few left" hint (no exact quantity is published). */
  low_stock?: boolean
  images?: import('./marketplace.types').ProductPhoto[]
  /** When present, the buyer picks one (each has its own price and availability). */
  variants?: import('./marketplace.types').PublicVariant[]
  category: StoreCategory
  company: { id: string; name: string; business_type?: string }
}

export type OrderStatus = 'PLACED' | 'CONFIRMED' | 'SHIPPED' | 'DELIVERED' | 'COMPLETED' | 'CANCELLED'
export type StorePaymentMethod = 'CASH_ON_DELIVERY' | 'MANUAL_TRANSFER'
export type StorePaymentStatus = 'UNPAID' | 'PAID' | 'REFUND_PENDING' | 'PARTIALLY_REFUNDED' | 'REFUNDED'

export interface OrderItem {
  id: string
  /** MERCHANDISE lines are products; SHIPPING and TAX are seller charges (no commission). */
  kind?: 'MERCHANDISE' | 'SHIPPING' | 'TAX'
  product_id: string | null
  variant_id?: string | null
  parent_item_id?: string | null
  sku_snapshot?: string
  variant_label_snapshot?: string
  image_url: string
  title_snapshot: string
  unit_price: string
  quantity: number
  line_total: string
  seller_discount: string
  platform_discount: string
  buyer_paid: string
  refunded_quantity: number
  refunded_buyer_paid: string
  /** Seller and finance views only. */
  merchandise_net?: string
  commission_rate?: string
  commission?: string
  seller_payable?: string
  refunded_commission?: string
  refunded_seller_payable?: string
}

export type ReturnStatus = 'REQUESTED' | 'APPROVED' | 'REJECTED' | 'RECEIVED' | 'REFUNDED'
export type DisputeStatus = 'OPEN' | 'RESOLVED_REFUND' | 'RESOLVED_REJECTED'

export interface ReturnRequest {
  id: string
  order: { id: string; number: string }
  status: ReturnStatus
  reason: string
  decision_note: string
  decided_at: string | null
  lines: { item: string; title: string; quantity: number }[]
  created_at: string
  updated_at: string
}

export interface Dispute {
  id: string
  order: { id: string; number: string }
  status: DisputeStatus
  reason: string
  resolution_note: string
  resolved_at: string | null
  created_at: string
}

export interface Order {
  id: string
  number: string
  checkout_number: string
  channel: 'B2C' | 'B2B'
  status: OrderStatus
  payment_method: StorePaymentMethod
  payment_status: StorePaymentStatus
  currency: string
  list_total: string
  seller_discount_total: string
  platform_discount_total: string
  total: string
  refunded_total: string
  merchant: { id: string; name: string }
  buyer_name: string
  delivery_governorate: { id: string; name_ar: string; name_en: string }
  delivery_city: { id: string; name_ar: string; name_en: string } | null
  delivery_address: string
  delivery_latitude?: string | null
  delivery_longitude?: string | null
  contact_phone: string
  note: string
  shipping_reference: string
  courier_name?: string
  shipping_total?: string
  shipping_min_days?: number | null
  shipping_max_days?: number | null
  tax_mode?: 'NONE' | 'INCLUSIVE' | 'EXCLUSIVE'
  tax_rate?: string
  tax_label?: string
  tax_registration_number?: string
  tax_total?: string
  tax_included_total?: string
  tracking_events?: TrackingEvent[]
  invoices?: InvoiceSummary[]
  paid_at: string | null
  shipped_at: string | null
  delivered_at: string | null
  completed_at: string | null
  items: OrderItem[]
  transitions: { from_status: string; to_status: string; reason: string; created_at: string }[]
  returns: ReturnRequest[]
  disputes: Dispute[]
  refunds: { id: string; amount: string; reason: string; created_at: string }[]
  return_deadline: string | null
  created_at: string
  status_changed_at: string | null
  /** Seller and finance views only: the 20% snapshot. */
  merchandise_net?: string
  commission_rate?: string
  commission_policy_version?: number | null
  commission_total?: string
  seller_payable_total?: string
  settlement_state?: 'NOT_ELIGIBLE' | 'ACCRUED'
  /** Finance view only. */
  buyer_email?: string
  payment_reference?: string
  payment_verified_by?: string
}

export type TrackingStatus = 'PICKED_UP' | 'IN_TRANSIT' | 'OUT_FOR_DELIVERY' | 'DELIVERY_ATTEMPTED' | 'DELAYED' | 'NOTE'

export interface TrackingEvent {
  id: string
  status: TrackingStatus
  note: string
  location: string
  created_at: string
}

export type InvoiceKind = 'INVOICE' | 'RECEIPT' | 'CREDIT_NOTE'

export interface InvoiceSummary {
  id: string
  kind: InvoiceKind
  number: string
  total: string
  created_at: string
}

export interface InvoiceLine {
  title: string
  variant: string
  sku: string
  quantity: number
  unit_price: string
  line_total: string
  seller_discount: string
  platform_discount: string
  tax: string
  total: string
  refunded_quantity: number
}

/** A frozen, issued document (later product or address edits never change it). */
export interface InvoiceDocument extends InvoiceSummary {
  snapshot: {
    kind: InvoiceKind
    issued_at: string
    currency: string
    notice: string
    operator: string
    seller: { name: string; business_type: string; address: string; governorate: string; phone: string; email: string; tax_registration_number: string }
    buyer: { name: string; address: string; governorate: string; city: string; phone: string }
    order: { number: string; checkout: string; placed_at: string; channel: string; payment_method: string; payment_reference: string; paid_at: string | null }
    lines: InvoiceLine[]
    tax: { mode: string; rate: string; label: string; added: string; included: string }
    totals: { list: string; seller_discount: string; platform_discount: string; shipping: string; tax: string; total: string; refunded: string }
    refund?: { amount: string; reason: string; executed_at: string }
  }
}

export interface CheckoutRequest {
  items: { product: string; variant?: string | null; quantity: number }[]
  coupons?: string[]
  /** One per press of "Place order": a retried request returns the first checkout. */
  idempotency_key: string
  payment_method: StorePaymentMethod
  governorate: string
  city?: string | null
  address: string
  phone: string
  note?: string
  /** Optional pin shared from the device (both or neither). */
  latitude?: string | null
  longitude?: string | null
}

export interface DeliveryDefaults {
  governorate: string | null
  city: string | null
  address: string
  phone: string
}

export type QuoteStatus = 'REQUESTED' | 'QUOTED' | 'ACCEPTED' | 'DECLINED' | 'WITHDRAWN' | 'ORDERED' | 'EXPIRED'

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
  expires_at?: string | null
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

/** Server-composed dashboard of one workspace (`GET /workspaces/dashboard?ws=`). */
export interface DashboardStat {
  key: string
  value: number | string | boolean | null
}

export interface DashboardItem {
  id: string
  title: string
  subtitle: string
  status: string
  status_group: string
  path: string
}

export interface DashboardModule {
  key: string
  variant: string
  stats: DashboardStat[]
  items: DashboardItem[]
  link: string
}

export interface WorkspaceDashboard {
  workspace: Pick<Workspace, 'id' | 'kind' | 'subtype' | 'title' | 'role' | 'verification_status' | 'org_id'>
  header: { name: string; since: string; reservations_enabled: boolean }
  actions: { key: string; path: string }[]
  modules: DashboardModule[]
  generated_at: string
}
