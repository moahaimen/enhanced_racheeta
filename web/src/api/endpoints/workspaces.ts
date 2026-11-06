import { apiRequest } from '../client'
import type {
  DeliveryDefaults,
  ListingPromotion,
  MarketingPreferences,
  Order,
  OrgMember,
  OrgRole,
  OrgSummary,
  PaginatedOrders,
  PaginatedPromotedListings,
  PaginatedPromotions,
  PaginatedQuotes,
  PaginatedStoreProducts,
  ProfessionGroup,
  Quote,
  StoreCategory,
  StoreProduct,
  Workspace,
  WorkspaceDashboard,
} from '../workspaces.types'

const enc = encodeURIComponent
type OrgKind = 'facility' | 'company'

/** `?company=` scopes merchant endpoints to a business the caller works for (server-checked). */
function companyQuery(companyId?: string, extra: Record<string, string> = {}): string {
  const q = new URLSearchParams(extra)
  if (companyId) q.set('company', companyId)
  const text = q.toString()
  return text ? `?${text}` : ''
}

// ---- workspaces ---------------------------------------------------------------------------------
export function listWorkspaces(signal?: AbortSignal): Promise<Workspace[]> {
  return apiRequest<Workspace[]>('/api/v1/workspaces', { signal })
}

/** The dashboard of one of MY workspaces; omit `ws` for my default. Unknown/foreign ids are 404. */
export function getWorkspaceDashboard(ws: string | null, signal?: AbortSignal): Promise<WorkspaceDashboard> {
  const q = ws ? `?ws=${enc(ws)}` : ''
  return apiRequest<WorkspaceDashboard>(`/api/v1/workspaces/dashboard${q}`, { signal })
}

export function getOrgSummary(kind: OrgKind, id: string, signal?: AbortSignal): Promise<OrgSummary> {
  return apiRequest<OrgSummary>(`/api/v1/workspaces/${kind}/${enc(id)}`, { signal })
}

export function listOrgMembers(kind: OrgKind, id: string, signal?: AbortSignal): Promise<OrgMember[]> {
  return apiRequest<OrgMember[]>(`/api/v1/workspaces/${kind}/${enc(id)}/members`, { signal })
}

export function addOrgMember(kind: OrgKind, id: string, email: string, role: Exclude<OrgRole, 'OWNER'>) {
  return apiRequest<OrgMember>(`/api/v1/workspaces/${kind}/${enc(id)}/members`, {
    method: 'POST',
    body: { email, role },
  })
}

export function endOrgMember(kind: OrgKind, id: string, memberId: string) {
  return apiRequest<OrgMember>(`/api/v1/workspaces/${kind}/${enc(id)}/members/${enc(memberId)}/end`, {
    method: 'POST',
  })
}

// ---- public store, cart and orders --------------------------------------------------------------
export function listStoreProducts(page = 1, category = '', signal?: AbortSignal, search = ''): Promise<PaginatedStoreProducts> {
  const q = new URLSearchParams({ page: String(page) })
  if (category) q.set('category', category)
  if (search) q.set('q', search)
  return apiRequest<PaginatedStoreProducts>(`/api/v1/store/products?${q.toString()}`, { auth: false, signal })
}

export function getStoreProduct(id: string, signal?: AbortSignal): Promise<StoreProduct> {
  return apiRequest<StoreProduct>(`/api/v1/store/products/${enc(id)}`, { auth: false, signal })
}

export function listStoreCategories(signal?: AbortSignal): Promise<StoreCategory[]> {
  return apiRequest<StoreCategory[]>('/api/v1/store/categories', { auth: false, signal })
}

/** My last delivery details (else my account phone) to pre-fill checkout. */
export function getDeliveryDefaults(signal?: AbortSignal): Promise<DeliveryDefaults> {
  return apiRequest<DeliveryDefaults>('/api/v1/orders/delivery-defaults', { signal })
}

export function listMyOrders(page = 1, signal?: AbortSignal): Promise<PaginatedOrders> {
  return apiRequest<PaginatedOrders>(`/api/v1/orders?page=${page}`, { signal })
}

export function cancelMyOrder(id: string, reason = ''): Promise<Order> {
  return apiRequest<Order>(`/api/v1/orders/${enc(id)}/cancel`, { method: 'POST', body: { reason } })
}

export function listMerchantOrders(companyId?: string, page = 1, signal?: AbortSignal): Promise<PaginatedOrders> {
  return apiRequest<PaginatedOrders>(
    `/api/v1/merchant/orders${companyQuery(companyId, { page: String(page) })}`,
    { signal },
  )
}


// ---- B2B quotes ---------------------------------------------------------------------------------
export function requestQuote(product: string, quantity: number, message = '', variant?: string | null): Promise<Quote> {
  return apiRequest<Quote>('/api/v1/quotes', { method: 'POST', body: variant ? { product, quantity, message, variant } : { product, quantity, message } })
}

export function listMyQuotes(page = 1, signal?: AbortSignal): Promise<PaginatedQuotes> {
  return apiRequest<PaginatedQuotes>(`/api/v1/quotes?page=${page}`, { signal })
}

export function closeMyQuote(id: string, outcome: 'ACCEPTED' | 'DECLINED' | 'WITHDRAWN'): Promise<Quote> {
  return apiRequest<Quote>(`/api/v1/quotes/${enc(id)}/close`, { method: 'POST', body: { outcome } })
}

export function listMerchantQuotes(companyId?: string, page = 1, signal?: AbortSignal): Promise<PaginatedQuotes> {
  return apiRequest<PaginatedQuotes>(
    `/api/v1/merchant/quotes${companyQuery(companyId, { page: String(page) })}`,
    { signal },
  )
}

export function respondQuote(id: string, unitPrice: string, note: string, companyId?: string) {
  return apiRequest<Quote>(`/api/v1/merchant/quotes/${enc(id)}/respond${companyQuery(companyId)}`, {
    method: 'POST',
    body: { unit_price: unitPrice, note },
  })
}

export function declineQuote(id: string, companyId?: string) {
  return apiRequest<Quote>(`/api/v1/merchant/quotes/${enc(id)}/decline${companyQuery(companyId)}`, {
    method: 'POST',
  })
}

// ---- preferences --------------------------------------------------------------------------------
export function getPreferences(signal?: AbortSignal): Promise<MarketingPreferences> {
  return apiRequest<MarketingPreferences>('/api/v1/me/preferences', { signal })
}

export function updatePreferences(changes: Partial<MarketingPreferences>): Promise<MarketingPreferences> {
  return apiRequest<MarketingPreferences>('/api/v1/me/preferences', { method: 'PATCH', body: changes })
}

// ---- real-estate promotions ---------------------------------------------------------------------
export function listPromotedListings(signal?: AbortSignal): Promise<PaginatedPromotedListings> {
  return apiRequest<PaginatedPromotedListings>('/api/v1/real-estate/promoted', { signal })
}

export function listMyPromotions(signal?: AbortSignal): Promise<PaginatedPromotions> {
  return apiRequest<PaginatedPromotions>('/api/v1/real-estate/owner/promotions', { signal })
}

export function requestPromotion(listing: string, targetProviderTypes: string[], days: number) {
  return apiRequest<ListingPromotion>('/api/v1/real-estate/owner/promotions', {
    method: 'POST',
    body: { listing, target_provider_types: targetProviderTypes, days },
  })
}

export function endPromotion(id: string) {
  return apiRequest<ListingPromotion>(`/api/v1/real-estate/owner/promotions/${enc(id)}/end`, { method: 'POST' })
}

export function listAdminPromotions(status = '', signal?: AbortSignal): Promise<PaginatedPromotions> {
  const q = status ? `?status=${enc(status)}` : ''
  return apiRequest<PaginatedPromotions>(`/api/v1/admin/real-estate/promotions${q}`, { signal })
}

export function approvePromotion(id: string) {
  return apiRequest<ListingPromotion>(`/api/v1/admin/real-estate/promotions/${enc(id)}/approve`, { method: 'POST' })
}

export function rejectPromotion(id: string, reason: string) {
  return apiRequest<ListingPromotion>(`/api/v1/admin/real-estate/promotions/${enc(id)}/reject`, {
    method: 'POST',
    body: { reason },
  })
}

// ---- jobs vocabulary ----------------------------------------------------------------------------
export function listProfessionGroups(signal?: AbortSignal): Promise<ProfessionGroup[]> {
  return apiRequest<ProfessionGroup[]>('/api/v1/jobs/professions', { auth: false, signal })
}

// ---- facility staff: reservations of a facility the caller works for ---------------------------
export function listFacilityReservations(facilityId: string, signal?: AbortSignal) {
  return apiRequest<import('../reservations.types').PaginatedProviderReservations>(
    `/api/v1/workspaces/facility/${enc(facilityId)}/reservations`,
    { signal },
  )
}

export function transitionFacilityReservation(
  facilityId: string,
  reservationId: string,
  status: import('../reservations.types').ReservationStatus,
) {
  return apiRequest<import('../reservations.types').ReservationProvider>(
    `/api/v1/workspaces/facility/${enc(facilityId)}/reservations/${enc(reservationId)}/transition`,
    { method: 'POST', body: { status } },
  )
}
