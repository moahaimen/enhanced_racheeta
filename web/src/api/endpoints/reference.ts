import { apiRequest } from '../client'
import type { City, Country, Governorate, Specialty } from '../providers.types'

export function listCountries(signal?: AbortSignal): Promise<Country[]> {
  return apiRequest<Country[]>('/api/v1/geo/countries', { auth: false, signal })
}

export function listGovernorates(countryId?: string, signal?: AbortSignal): Promise<Governorate[]> {
  const qs = countryId ? `?country=${encodeURIComponent(countryId)}` : ''
  return apiRequest<Governorate[]>(`/api/v1/geo/governorates${qs}`, { auth: false, signal })
}

export function listCities(governorateId: string, signal?: AbortSignal): Promise<City[]> {
  return apiRequest<City[]>(`/api/v1/geo/cities?governorate=${encodeURIComponent(governorateId)}`, {
    auth: false,
    signal,
  })
}

export function listSpecialties(signal?: AbortSignal): Promise<Specialty[]> {
  return apiRequest<Specialty[]>('/api/v1/specialties', { auth: false, signal })
}
