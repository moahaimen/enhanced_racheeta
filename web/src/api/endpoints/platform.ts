import { apiRequest } from '../client'

/** Server-controlled product switches (backend apps.core.features). Public, never per-user. */
export interface PlatformFeatures {
  reservations_enabled: boolean
}

export function getFeatures(signal?: AbortSignal): Promise<PlatformFeatures> {
  return apiRequest<PlatformFeatures>('/api/v1/platform/features', { auth: false, signal })
}
