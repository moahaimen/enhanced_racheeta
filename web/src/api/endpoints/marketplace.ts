import { apiRequest } from '../client'
import type {
  CompanyDashboard,
  CompanyProduct,
  CompanyWrite,
  MarketplaceProduct,
  MedicalCompany,
  PaginatedCompanyProducts,
  PaginatedMarketplaceProducts,
  ProductCategory,
  ProductWrite,
} from '../marketplace.types'

const enc = encodeURIComponent

export function listCategories(signal?: AbortSignal): Promise<ProductCategory[]> {
  return apiRequest<ProductCategory[]>('/api/v1/marketplace/categories', { auth: false, signal })
}

/** Products the BACKEND targets at the caller's provider profile; no client-side filtering. */
export function listTargetedProducts(
  page = 1,
  category = '',
  signal?: AbortSignal,
): Promise<PaginatedMarketplaceProducts> {
  const q = new URLSearchParams({ page: String(page) })
  if (category) q.set('category', category)
  return apiRequest<PaginatedMarketplaceProducts>(`/api/v1/marketplace/products?${q.toString()}`, { signal })
}

export function getTargetedProduct(id: string, signal?: AbortSignal): Promise<MarketplaceProduct> {
  return apiRequest<MarketplaceProduct>(`/api/v1/marketplace/products/${enc(id)}`, { signal })
}

export function getMyCompany(signal?: AbortSignal): Promise<MedicalCompany> {
  return apiRequest<MedicalCompany>('/api/v1/marketplace/company', { signal })
}

export function createMyCompany(payload: CompanyWrite): Promise<MedicalCompany> {
  return apiRequest<MedicalCompany>('/api/v1/marketplace/company', { method: 'POST', body: payload })
}

export function updateMyCompany(payload: CompanyWrite): Promise<MedicalCompany> {
  return apiRequest<MedicalCompany>('/api/v1/marketplace/company', { method: 'PATCH', body: payload })
}

export function requestCompanyVerification(): Promise<MedicalCompany> {
  return apiRequest<MedicalCompany>('/api/v1/marketplace/company/verification/request', { method: 'POST' })
}

export function getCompanyDashboard(signal?: AbortSignal): Promise<CompanyDashboard> {
  return apiRequest<CompanyDashboard>('/api/v1/marketplace/company/dashboard', { signal })
}

export function listMyProducts(page = 1, signal?: AbortSignal): Promise<PaginatedCompanyProducts> {
  return apiRequest<PaginatedCompanyProducts>(`/api/v1/marketplace/company/products?page=${page}`, { signal })
}

export function createMyProduct(payload: ProductWrite): Promise<CompanyProduct> {
  return apiRequest<CompanyProduct>('/api/v1/marketplace/company/products', { method: 'POST', body: payload })
}

export function updateMyProduct(id: string, payload: ProductWrite): Promise<CompanyProduct> {
  return apiRequest<CompanyProduct>(`/api/v1/marketplace/company/products/${enc(id)}`, { method: 'PATCH', body: payload })
}

export function setMyProductActive(id: string, active: boolean): Promise<CompanyProduct> {
  return apiRequest<CompanyProduct>(
    `/api/v1/marketplace/company/products/${enc(id)}/${active ? 'activate' : 'deactivate'}`,
    { method: 'POST' },
  )
}
