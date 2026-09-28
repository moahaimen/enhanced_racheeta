import type { Paginated } from './providers.types'

export interface PublicReview {
  id: string
  provider_name_snapshot: string
  service_title_snapshot: string
  rating: number
  comment: string
  created_at: string
}

export interface MyReview extends PublicReview {
  reservation_id: string
  provider_id: string | null
}

export interface PublicOffer {
  id: string
  service_title_snapshot: string
  title: string
  description: string
  original_price_snapshot: string
  offer_price: string
  currency_snapshot: string
  starts_at: string
  ends_at: string
}

export interface ProviderOffer extends PublicOffer {
  service_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type PaginatedReviews = Paginated<PublicReview>
export type PaginatedMyReviews = Paginated<MyReview>
export type PaginatedProviderOffers = Paginated<ProviderOffer>
