import { apiRequest } from '../client'
import type {
  Membership,
  Paginated,
  ProviderCard,
  ProviderListParams,
  ProviderOwner,
  ProviderPublic,
  ProviderWrite,
  ServiceOffering,
  ServiceWrite,
} from '../providers.types'

export function buildQuery(params: object): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params as Record<string, unknown>)) {
    if (value === undefined || value === '' || value === null) continue
    search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

// ---- public -------------------------------------------------------------

export function listProviders(
  params: ProviderListParams = {},
  signal?: AbortSignal,
): Promise<Paginated<ProviderCard>> {
  return apiRequest<Paginated<ProviderCard>>(`/api/v1/providers${buildQuery(params)}`, {
    auth: false,
    signal,
  })
}

export function getProvider(id: string, signal?: AbortSignal): Promise<ProviderPublic> {
  return apiRequest<ProviderPublic>(`/api/v1/providers/${encodeURIComponent(id)}`, {
    auth: false,
    signal,
  })
}

// ---- self-management ----------------------------------------------------

export function getMyProvider(signal?: AbortSignal): Promise<ProviderOwner> {
  return apiRequest<ProviderOwner>('/api/v1/providers/me', { signal })
}

export function createMyProvider(payload: ProviderWrite): Promise<ProviderOwner> {
  return apiRequest<ProviderOwner>('/api/v1/providers/me', { method: 'POST', body: payload })
}

export function updateMyProvider(payload: ProviderWrite): Promise<ProviderOwner> {
  return apiRequest<ProviderOwner>('/api/v1/providers/me', { method: 'PATCH', body: payload })
}

export function requestVerification(): Promise<ProviderOwner> {
  return apiRequest<ProviderOwner>('/api/v1/providers/me/verification/request', { method: 'POST' })
}

export function listMyServices(signal?: AbortSignal): Promise<ServiceOffering[]> {
  return apiRequest<ServiceOffering[]>('/api/v1/providers/me/services', { signal })
}

export function createMyService(payload: ServiceWrite): Promise<ServiceOffering> {
  return apiRequest<ServiceOffering>('/api/v1/providers/me/services', { method: 'POST', body: payload })
}

export function updateMyService(id: string, payload: ServiceWrite): Promise<ServiceOffering> {
  return apiRequest<ServiceOffering>(`/api/v1/providers/me/services/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: payload,
  })
}

export function deleteMyService(id: string): Promise<void> {
  return apiRequest<void>(`/api/v1/providers/me/services/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
}

export function listMyMemberships(signal?: AbortSignal): Promise<Membership[]> {
  return apiRequest<Membership[]>('/api/v1/providers/me/memberships', { signal })
}

export function createMembership(counterpart: string, roleTitle = ''): Promise<Membership> {
  return apiRequest<Membership>('/api/v1/providers/me/memberships', {
    method: 'POST',
    body: { counterpart, role_title: roleTitle },
  })
}

export function membershipAction(id: string, action: 'accept' | 'reject' | 'end'): Promise<Membership> {
  return apiRequest<Membership>(`/api/v1/providers/me/memberships/${encodeURIComponent(id)}/${action}`, {
    method: 'POST',
  })
}
