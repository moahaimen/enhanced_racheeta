import type { Paginated } from './providers.types'
import type { Order, ReturnRequest, Dispute } from './workspaces.types'

/** Server price of a cart (nothing here is computed by the browser). */
export interface PreviewLine {
  product: string
  title: string
  image_url: string
  quantity: number
  unit_price: string
  line_total: string
  seller_discount: string
  platform_discount: string
  buyer_paid: string
  channel: 'B2C' | 'B2B'
}

export interface PreviewOrder {
  merchant: { id: string; name: string }
  seller_coupon: string | null
  lines: PreviewLine[]
  list_total: string
  seller_discount_total: string
  platform_discount_total: string
  total: string
}

export interface CheckoutPreview {
  currency: string
  orders: PreviewOrder[]
  platform_coupon: string | null
  list_total: string
  seller_discount_total: string
  platform_discount_total: string
  total: string
}

export interface CheckoutResult {
  id: string
  number: string
  currency: string
  list_total: string
  seller_discount_total: string
  platform_discount_total: string
  total: string
  orders: Order[]
  created_at: string
}

export interface InventoryRow {
  id: string
  title: string
  image_url: string
  is_active: boolean
  price: string | null
  on_hand: number | null
  reserved: number
  available: number | null
  reorder_threshold: number | null
  low: boolean
}

export interface StockMovement {
  id: string
  kind: 'RESERVE' | 'RELEASE' | 'CONSUME' | 'RESTOCK' | 'ADJUST'
  quantity: number
  on_hand_after: number
  reserved_after: number
  order_number: string
  reason: string
  created_at: string
}

export type DiscountKind = 'PERCENT' | 'FIXED'

export interface Coupon {
  id: string
  code: string
  funded_by: 'SELLER' | 'PLATFORM'
  company: { id: string; name: string } | null
  kind: DiscountKind
  value: string
  max_discount: string | null
  min_subtotal: string
  starts_at: string
  ends_at: string
  max_redemptions: number | null
  redemptions: number
  is_active: boolean
  created_at: string
}

export interface CouponInput {
  code: string
  kind: DiscountKind
  value: string
  max_discount?: string | null
  min_subtotal?: string
  ends_at: string
  max_redemptions?: number | null
}

export interface ProductSale {
  id: string
  product: { id: string; title: string }
  percent: string
  starts_at: string
  ends_at: string
  is_active: boolean
  created_at: string
}

export interface Settlement {
  id: string
  company: { id: string; name: string }
  currency: string
  amount: string
  status: 'DRAFT' | 'PAID' | 'CANCELLED'
  reference_note: string
  confirmed_by: string
  confirmed_at: string | null
  created_at: string
}

export interface StatementEntry {
  reference: string
  kind: 'PAYMENT' | 'ACCRUAL' | 'REFUND' | 'PAYOUT' | 'RECOVERY'
  account: 'SELLER_PAYABLE' | 'SELLER_RECEIVABLE'
  order_number: string
  memo: string
  debit: string
  credit: string
  created_at: string
}

export interface MerchantStatement {
  currency: string
  commission_rate: string
  gross_sales: string
  seller_discounts: string
  merchandise_net: string
  commission: string
  refunded_commission: string
  refunded_seller_payable: string
  seller_earnings: string
  paid_out: string
  payable: string
  /** What the seller owes Racheeta (a refund after its payout, not yet offset). */
  receivable: string
  recovered: string
  pending_orders: number
  pending_seller_payable: string
  draft_settlement: { id: string; amount: string } | null
  entries: StatementEntry[]
  settlements: Settlement[]
}

export interface ReconciliationCheck {
  name: string
  expected: string
  actual: string
  ok: boolean
}

export interface Reconciliation {
  currency: string
  ok: boolean
  checks: ReconciliationCheck[]
  balances: Record<string, string>
  totals: Record<string, number>
}

export interface LedgerEntry {
  id: string
  reference: string
  kind: StatementEntry['kind']
  currency: string
  memo: string
  order_number: string
  lines: { account: string; company: { id: string; name: string } | null; debit: string; credit: string }[]
  created_at: string
}

export interface SellerPayable {
  company: { id: string; name: string }
  payable: string
  receivable: string
  draft_settlement: { id: string; amount: string } | null
}

export interface CommissionPolicy {
  version: number
  rate_percent: string
  effective_from: string
  note: string
  created_at: string
}

export type PaginatedLedgerEntries = Paginated<LedgerEntry>
export type PaginatedSettlements = Paginated<Settlement>
export type PaginatedCoupons = Paginated<Coupon>
export type PaginatedProductSales = Paginated<ProductSale>
export type PaginatedStockMovements = Paginated<StockMovement>
export type PaginatedReturns = Paginated<ReturnRequest>
export type PaginatedDisputes = Paginated<Dispute>
export type PaginatedAdminOrders = Paginated<Order>

export interface SellerRecovery {
  id: string
  company: { id: string; name: string }
  currency: string
  amount: string
  reference_note: string
  created_at: string
}
