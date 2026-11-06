import { apiRequest } from '../client'
import type {
  ListingFilters,
  ListingInquiry,
  ListingWrite,
  InquiryStatus,
  OwnerDashboard,
  OwnerInquiry,
  PaginatedInquiries,
  PaginatedOwnerInquiries,
  OwnerListing,
  PaginatedListings,
  PaginatedOwnerListings,
  PropertyListing,
  RealEstateSeller,
  SellerWrite,
} from '../realEstate.types'

const enc = encodeURIComponent
const BASE = '/api/v1/real-estate'

function query(filters: ListingFilters): string {
  const q = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === '' || value === 1) continue
    q.set(key, String(value))
  }
  const text = q.toString()
  return text ? `?${text}` : ''
}

/** Public catalogue: the BACKEND decides visibility and applies every filter. */
export function listListings(filters: ListingFilters = {}, signal?: AbortSignal): Promise<PaginatedListings> {
  return apiRequest<PaginatedListings>(`${BASE}/listings${query(filters)}`, { auth: false, signal })
}

export function getListing(id: string, signal?: AbortSignal): Promise<PropertyListing> {
  return apiRequest<PropertyListing>(`${BASE}/listings/${enc(id)}`, { auth: false, signal })
}

export function getMySeller(signal?: AbortSignal): Promise<RealEstateSeller> {
  return apiRequest<RealEstateSeller>(`${BASE}/owner`, { signal })
}

export function createMySeller(payload: SellerWrite): Promise<RealEstateSeller> {
  return apiRequest<RealEstateSeller>(`${BASE}/owner`, { method: 'POST', body: payload })
}

export function updateMySeller(payload: SellerWrite): Promise<RealEstateSeller> {
  return apiRequest<RealEstateSeller>(`${BASE}/owner`, { method: 'PATCH', body: payload })
}

export function getOwnerDashboard(signal?: AbortSignal): Promise<OwnerDashboard> {
  return apiRequest<OwnerDashboard>(`${BASE}/owner/dashboard`, { signal })
}

export function listMyListings(page = 1, signal?: AbortSignal): Promise<PaginatedOwnerListings> {
  return apiRequest<PaginatedOwnerListings>(`${BASE}/owner/listings?page=${page}`, { signal })
}

export function createMyListing(payload: ListingWrite): Promise<OwnerListing> {
  return apiRequest<OwnerListing>(`${BASE}/owner/listings`, { method: 'POST', body: payload })
}

export function updateMyListing(id: string, payload: ListingWrite): Promise<OwnerListing> {
  return apiRequest<OwnerListing>(`${BASE}/owner/listings/${enc(id)}`, { method: 'PATCH', body: payload })
}

/** Publication is a server decision: the backend gate answers with typed per-field codes when it refuses. */
export function setMyListingPublished(id: string, published: boolean): Promise<OwnerListing> {
  return apiRequest<OwnerListing>(`${BASE}/owner/listings/${enc(id)}/${published ? 'publish' : 'unpublish'}`, {
    method: 'POST',
  })
}

// ---- inquiries ----------------------------------------------------------------------------

/** Signed-in accounts only; the backend accepts it only for a publicly visible listing. */
export function sendInquiry(listingId: string, message: string, shareContact: boolean): Promise<ListingInquiry> {
  return apiRequest<ListingInquiry>(`${BASE}/listings/${enc(listingId)}/inquiries`, {
    method: 'POST',
    body: { message, share_contact: shareContact },
  })
}

export function listMyInquiries(page = 1, signal?: AbortSignal): Promise<PaginatedInquiries> {
  return apiRequest<PaginatedInquiries>(`${BASE}/inquiries/mine?page=${page}`, { signal })
}

export function withdrawMyInquiry(id: string): Promise<ListingInquiry> {
  return apiRequest<ListingInquiry>(`${BASE}/inquiries/mine/${enc(id)}/withdraw`, { method: 'POST' })
}

export function listOwnerInquiries(
  filters: { status?: InquiryStatus | ''; page?: number } = {},
  signal?: AbortSignal,
): Promise<PaginatedOwnerInquiries> {
  const q = new URLSearchParams()
  if (filters.status) q.set('status', filters.status)
  if (filters.page && filters.page > 1) q.set('page', String(filters.page))
  const text = q.toString()
  return apiRequest<PaginatedOwnerInquiries>(`${BASE}/owner/inquiries${text ? `?${text}` : ''}`, { signal })
}

export function respondToInquiry(id: string, response: string): Promise<OwnerInquiry> {
  return apiRequest<OwnerInquiry>(`${BASE}/owner/inquiries/${enc(id)}/respond`, { method: 'POST', body: { response } })
}

export function closeInquiry(id: string): Promise<OwnerInquiry> {
  return apiRequest<OwnerInquiry>(`${BASE}/owner/inquiries/${enc(id)}/close`, { method: 'POST' })
}
