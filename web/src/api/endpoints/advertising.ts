import { apiRequest } from '../client'
import type {
  AdminCampaign,
  Campaign,
  CampaignDashboard,
  CampaignQuote,
  CampaignStatus,
  CampaignWrite,
  PaginatedAdminCampaigns,
  PaginatedCampaigns,
  PaginatedSponsored,
  PaymentVerification,
} from '../advertising.types'
import { buildQuery } from './providers'

const enc = encodeURIComponent
const COMPANY = '/api/v1/advertising/company'
const ADMIN = '/api/v1/admin/advertising/campaigns'

/** Sponsored campaigns the BACKEND targets at the caller's provider profile; no client-side filtering. */
export function listSponsored(page = 1, signal?: AbortSignal): Promise<PaginatedSponsored> {
  return apiRequest<PaginatedSponsored>(`/api/v1/advertising/marketplace${buildQuery({ page })}`, { signal })
}

export function getCampaignDashboard(signal?: AbortSignal): Promise<CampaignDashboard> {
  return apiRequest<CampaignDashboard>(`${COMPANY}/dashboard`, { signal })
}

export function listMyCampaigns(page = 1, signal?: AbortSignal): Promise<PaginatedCampaigns> {
  return apiRequest<PaginatedCampaigns>(`${COMPANY}/campaigns${buildQuery({ page })}`, { signal })
}

export function createCampaign(payload: CampaignWrite): Promise<Campaign> {
  return apiRequest<Campaign>(`${COMPANY}/campaigns`, { method: 'POST', body: payload })
}

export function updateCampaign(id: string, payload: CampaignWrite): Promise<Campaign> {
  return apiRequest<Campaign>(`${COMPANY}/campaigns/${enc(id)}`, { method: 'PATCH', body: payload })
}

/** The backend prices the campaign under lock and creates its payment record; the browser sends no price. */
export function submitCampaign(id: string): Promise<Campaign> {
  return apiRequest<Campaign>(`${COMPANY}/campaigns/${enc(id)}/submit`, { method: 'POST' })
}

export function cancelCampaign(id: string): Promise<Campaign> {
  return apiRequest<Campaign>(`${COMPANY}/campaigns/${enc(id)}/cancel`, { method: 'POST' })
}

/** Price preview from the current backend rate. Never sent back on submission. */
export function quoteCampaign(dates: { starts_on: string; ends_on: string }, signal?: AbortSignal): Promise<CampaignQuote> {
  return apiRequest<CampaignQuote>(`${COMPANY}/quote`, { method: 'POST', body: dates, signal })
}

export function listAdminCampaigns(
  params: { status?: CampaignStatus | ''; payment_status?: string; company?: string; page?: number } = {},
  signal?: AbortSignal,
): Promise<PaginatedAdminCampaigns> {
  return apiRequest<PaginatedAdminCampaigns>(`${ADMIN}${buildQuery(params)}`, { signal })
}

/** Administrator: confirms the off-platform payment. Only method, reference and note are sent. */
export function verifyCampaignPayment(id: string, payload: PaymentVerification): Promise<AdminCampaign> {
  return apiRequest<AdminCampaign>(`${ADMIN}/${enc(id)}/verify-payment`, { method: 'POST', body: payload })
}

export function rejectCampaignPayment(id: string, reason: string): Promise<AdminCampaign> {
  return apiRequest<AdminCampaign>(`${ADMIN}/${enc(id)}/reject-payment`, { method: 'POST', body: { reason } })
}
