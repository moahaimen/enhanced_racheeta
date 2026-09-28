import { apiRequest } from '../client'
import type { PaginatedProviderOffers, PaginatedPublicOffers, ProviderOffer } from '../engagement.types'

export interface OfferCreate {
  service: string
  title: string
  description?: string
  offer_price: string
  starts_at: string
  ends_at: string
}

export interface OfferUpdate {
  title?: string
  description?: string
  offer_price?: string
  starts_at?: string
  ends_at?: string
  is_active?: boolean
}

export function listPublicOffers(
  providerId: string,
  page = 1,
  signal?: AbortSignal,
): Promise<PaginatedPublicOffers> {
  return apiRequest<PaginatedPublicOffers>(
    `/api/v1/providers/${encodeURIComponent(providerId)}/offers?page=${page}`,
    { auth: false, signal },
  )
}

export function listProviderOffers(
  page = 1,
  signal?: AbortSignal,
): Promise<PaginatedProviderOffers> {
  return apiRequest<PaginatedProviderOffers>(`/api/v1/offers/provider?page=${page}`, { signal })
}

export function createProviderOffer(payload: OfferCreate): Promise<ProviderOffer> {
  return apiRequest<ProviderOffer>('/api/v1/offers/provider', {
    method: 'POST',
    body: payload,
  })
}

export function updateProviderOffer(id: string, payload: OfferUpdate): Promise<ProviderOffer> {
  return apiRequest<ProviderOffer>(`/api/v1/offers/provider/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: payload,
  })
}
