import { apiRequest } from '../client'
import type {
  CheckoutPreview,
  CheckoutResult,
  CommissionPolicy,
  Coupon,
  CouponInput,
  InventoryRow,
  MarketplaceReport,
  MerchantStatement,
  PaginatedAdminOrders,
  PaginatedCoupons,
  PaginatedDisputes,
  PaginatedLedgerEntries,
  PaginatedProductSales,
  PaginatedReturns,
  PaginatedSettlements,
  PaginatedStockMovements,
  ProductSale,
  Reconciliation,
  SalesReport,
  SellerPayable,
  SellerRecovery,
  Settlement,
} from '../commerce.types'
import type {
  CheckoutRequest,
  InvoiceDocument,
  InvoiceSummary,
  Order,
  ReturnRequest,
  TrackingEvent,
  TrackingStatus,
} from '../workspaces.types'

const enc = encodeURIComponent

function q(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value) search.set(key, value)
  const text = search.toString()
  return text ? `?${text}` : ''
}

const post = <T,>(url: string, body: unknown = {}) => apiRequest<T>(url, { method: 'POST', body })

// ---- buyer ----------------------------------------------------------------------------------------
export function previewCheckout(items: CheckoutRequest['items'], coupons: string[], signal?: AbortSignal, governorate?: string) {
  const body = governorate ? { items, coupons, governorate } : { items, coupons }
  return apiRequest<CheckoutPreview>('/api/v1/checkouts/preview', { method: 'POST', body, signal })
}
export const listMyInvoices = (orderId: string, signal?: AbortSignal) =>
  apiRequest<InvoiceSummary[]>(`/api/v1/orders/${enc(orderId)}/invoices`, { signal })
export const getMyInvoice = (orderId: string, invoiceId: string, signal?: AbortSignal) =>
  apiRequest<InvoiceDocument>(`/api/v1/orders/${enc(orderId)}/invoices/${enc(invoiceId)}`, { signal })
export const listSellerInvoices = (orderId: string, company?: string, signal?: AbortSignal) =>
  apiRequest<InvoiceSummary[]>(`/api/v1/merchant/orders/${enc(orderId)}/invoices${q({ company })}`, { signal })
export const getSellerInvoice = (orderId: string, invoiceId: string, company?: string, signal?: AbortSignal) =>
  apiRequest<InvoiceDocument>(`/api/v1/merchant/orders/${enc(orderId)}/invoices/${enc(invoiceId)}${q({ company })}`, { signal })
export const addTracking = (orderId: string, body: { status: TrackingStatus; note?: string; location?: string }, company?: string) =>
  post<TrackingEvent>(`/api/v1/merchant/orders/${enc(orderId)}/tracking${q({ company })}`, body)
export const getSalesReport = (range: { from?: string; to?: string }, company?: string, signal?: AbortSignal) =>
  apiRequest<SalesReport>(`/api/v1/merchant/reports/sales${q({ ...range, company })}`, { signal })
export const downloadSalesReport = (range: { from?: string; to?: string }, company?: string) =>
  apiRequest<Blob>(`/api/v1/merchant/reports/sales${q({ ...range, company, export: 'csv' })}`, { responseType: 'blob' })
export const getMarketplaceReport = (range: { from?: string; to?: string }, signal?: AbortSignal) =>
  apiRequest<MarketplaceReport>(`/api/v1/admin/commerce/reports/marketplace${q(range)}`, { signal })
export const downloadMarketplaceReport = (range: { from?: string; to?: string }) =>
  apiRequest<Blob>(`/api/v1/admin/commerce/reports/marketplace${q({ ...range, export: 'csv' })}`, { responseType: 'blob' })
export const placeCheckout = (payload: CheckoutRequest) => post<CheckoutResult>('/api/v1/checkouts', payload)
export const confirmDelivery = (id: string) => post<Order>(`/api/v1/orders/${enc(id)}/confirm-delivery`)
export const requestReturn = (id: string, lines: { item: string; quantity: number }[], reason: string) =>
  post<Order>(`/api/v1/orders/${enc(id)}/returns`, { lines, reason })
export const openDispute = (id: string, reason: string) => post<Order>(`/api/v1/orders/${enc(id)}/disputes`, { reason })
export const orderFromQuote = (id: string, payload: Omit<CheckoutRequest, 'items' | 'coupons'>) =>
  post<CheckoutResult>(`/api/v1/quotes/${enc(id)}/order`, payload)

// ---- seller (owner or staff with ?company=) ---------------------------------------------------------
export const moveOrder = (id: string, status: 'CONFIRMED' | 'SHIPPED' | 'CANCELLED', company?: string, extra: { reason?: string; shipping_reference?: string; courier_name?: string } = {}) =>
  post<Order>(`/api/v1/merchant/orders/${enc(id)}/transition${q({ company })}`, { status, ...extra })
export const listSellerReturns = (company?: string, signal?: AbortSignal) =>
  apiRequest<PaginatedReturns>(`/api/v1/merchant/returns${q({ company })}`, { signal })
export const decideReturn = (id: string, approve: boolean, company?: string, note = '') =>
  post<ReturnRequest>(`/api/v1/merchant/returns/${enc(id)}/decide${q({ company })}`, { approve, note })
export const receiveReturn = (id: string, company?: string) =>
  post<ReturnRequest>(`/api/v1/merchant/returns/${enc(id)}/received${q({ company })}`)
export const listInventory = (company?: string, signal?: AbortSignal) =>
  apiRequest<InventoryRow[]>(`/api/v1/merchant/inventory${q({ company })}`, { signal })
export const adjustStock = (id: string, delta: number, reason: string, company?: string, variant?: string | null) =>
  post<InventoryRow>(`/api/v1/merchant/inventory/${enc(id)}/adjust${q({ company })}`, { delta, reason, variant_id: variant ?? null })
export const setReorderLevel = (id: string, threshold: number | null, company?: string, variant?: string | null) =>
  post<InventoryRow>(`/api/v1/merchant/inventory/${enc(id)}/threshold${q({ company })}`, { threshold, variant_id: variant ?? null })
export const listMovements = (id: string, company?: string, signal?: AbortSignal) =>
  apiRequest<PaginatedStockMovements>(`/api/v1/merchant/inventory/${enc(id)}/movements${q({ company })}`, { signal })
export const listSellerCoupons = (company?: string, signal?: AbortSignal) =>
  apiRequest<PaginatedCoupons>(`/api/v1/merchant/coupons${q({ company })}`, { signal })
export const createSellerCoupon = (input: CouponInput, company?: string) =>
  post<Coupon>(`/api/v1/merchant/coupons${q({ company })}`, input)
export const stopSellerCoupon = (id: string, company?: string) =>
  post<Coupon>(`/api/v1/merchant/coupons/${enc(id)}/deactivate${q({ company })}`)
export const listSales = (company?: string, signal?: AbortSignal) =>
  apiRequest<PaginatedProductSales>(`/api/v1/merchant/offers${q({ company })}`, { signal })
export const createSale = (product: string, percent: string, ends_at: string, company?: string) =>
  post<ProductSale>(`/api/v1/merchant/offers${q({ company })}`, { product, percent, ends_at })
export const stopSale = (id: string, company?: string) =>
  post<ProductSale>(`/api/v1/merchant/offers/${enc(id)}/deactivate${q({ company })}`)
export const getStatement = (company?: string, signal?: AbortSignal) =>
  apiRequest<MerchantStatement>(`/api/v1/merchant/finance${q({ company })}`, { signal })

// ---- Racheeta finance --------------------------------------------------------------------------------
export const listAdminOrders = (filters: Record<string, string | undefined>, page = 1, signal?: AbortSignal) =>
  apiRequest<PaginatedAdminOrders>(`/api/v1/admin/commerce/orders${q({ ...filters, page: String(page) })}`, { signal })
export const verifyPayment = (id: string, reference: string) =>
  post<Order>(`/api/v1/admin/commerce/orders/${enc(id)}/verify-payment`, { reference })
export const financeConfirmDelivery = (id: string) => post<Order>(`/api/v1/admin/commerce/orders/${enc(id)}/confirm-delivery`)
export const completeOrder = (id: string) => post<Order>(`/api/v1/admin/commerce/orders/${enc(id)}/complete`)
export const refundCancelled = (id: string) => post<Order>(`/api/v1/admin/commerce/orders/${enc(id)}/refund-cancelled`)
export const listAdminReturns = (status?: string, signal?: AbortSignal) =>
  apiRequest<PaginatedReturns>(`/api/v1/admin/commerce/returns${q({ status })}`, { signal })
export const refundReturn = (id: string) => post<Order>(`/api/v1/admin/commerce/returns/${enc(id)}/refund`)
export const listDisputes = (status?: string, signal?: AbortSignal) =>
  apiRequest<PaginatedDisputes>(`/api/v1/admin/commerce/disputes${q({ status })}`, { signal })
export const resolveDispute = (id: string, refund: boolean, note: string) =>
  post<Order>(`/api/v1/admin/commerce/disputes/${enc(id)}/resolve`, { refund, note })
export const listAllCoupons = (signal?: AbortSignal) => apiRequest<PaginatedCoupons>('/api/v1/admin/commerce/coupons', { signal })
export const createPlatformCoupon = (input: CouponInput) => post<Coupon>('/api/v1/admin/commerce/coupons', input)
export const stopPlatformCoupon = (id: string) => post<Coupon>(`/api/v1/admin/commerce/coupons/${enc(id)}/deactivate`)
export const getReconciliation = (signal?: AbortSignal) => apiRequest<Reconciliation>('/api/v1/admin/ledger/reconciliation', { signal })
export const listLedgerEntries = (page = 1, kind?: string, signal?: AbortSignal) =>
  apiRequest<PaginatedLedgerEntries>(`/api/v1/admin/ledger/entries${q({ page: String(page), kind })}`, { signal })
export const listPayables = (signal?: AbortSignal) => apiRequest<SellerPayable[]>('/api/v1/admin/ledger/payables', { signal })
export const listSettlements = (signal?: AbortSignal) => apiRequest<PaginatedSettlements>('/api/v1/admin/ledger/settlements', { signal })
export const prepareSettlement = (company: string) => post<Settlement>('/api/v1/admin/ledger/settlements/prepare', { company })
export const confirmSettlement = (id: string, reference_note: string) =>
  post<Settlement>(`/api/v1/admin/ledger/settlements/${enc(id)}/confirm`, { reference_note })
export const cancelSettlement = (id: string) => post<Settlement>(`/api/v1/admin/ledger/settlements/${enc(id)}/cancel`)
export const listPolicies = (signal?: AbortSignal) => apiRequest<CommissionPolicy[]>('/api/v1/admin/ledger/policy', { signal })
export const getSellerStatement = (company: string, signal?: AbortSignal) =>
  apiRequest<MerchantStatement>(`/api/v1/admin/ledger/statements/${enc(company)}`, { signal })
export const recordRecovery = (company: string, amount: string, reference_note: string) =>
  post<SellerRecovery>('/api/v1/admin/ledger/recoveries', { company, amount, reference_note })
