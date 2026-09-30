import { apiRequest } from '../client'
import type {
  ListingFilters,
  ListingWrite,
  OwnerDashboard,
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
