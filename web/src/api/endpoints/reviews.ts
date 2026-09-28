import { apiRequest } from '../client'
import type { MyReview, PaginatedMyReviews, PaginatedReviews } from '../engagement.types'

export function listPublicReviews(
  providerId: string,
  page = 1,
  signal?: AbortSignal,
): Promise<PaginatedReviews> {
  return apiRequest<PaginatedReviews>(
    `/api/v1/providers/${encodeURIComponent(providerId)}/reviews?page=${page}`,
    { auth: false, signal },
  )
}

export function createReview(
  reservation: string,
  rating: number,
  comment = '',
): Promise<MyReview> {
  return apiRequest<MyReview>('/api/v1/reviews', {
    method: 'POST',
    body: { reservation, rating, comment },
  })
}

export function listMyReviews(page = 1, signal?: AbortSignal): Promise<PaginatedMyReviews> {
  return apiRequest<PaginatedMyReviews>(`/api/v1/reviews/me?page=${page}`, { signal })
}
