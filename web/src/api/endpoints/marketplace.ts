import { apiRequest } from '../client'
import type {
  OwnerVariant,
  ProductPhoto,
  SellerDocument,
  SellerDocumentKind,
  ShippingRate,
  StoreSettings,
  VariantWrite,
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

// ---- seller onboarding and store management (owner, or staff with ?company=) ------------------
function withCompany(path: string, company?: string): string {
  return company ? `${path}${path.includes('?') ? '&' : '?'}company=${enc(company)}` : path
}

/** A pharmacy opens its store from its pharmacy provider profile (it stays a provider). */
export function openPharmacyStore(payload: { name?: string; description?: string } = {}): Promise<MedicalCompany> {
  return apiRequest<MedicalCompany>('/api/v1/marketplace/pharmacy-store', { method: 'POST', body: payload })
}

export function getStore(company?: string, signal?: AbortSignal): Promise<MedicalCompany> {
  return apiRequest<MedicalCompany>(withCompany('/api/v1/marketplace/company/store', company), { signal })
}

export function updateStoreSettings(payload: StoreSettings, company?: string): Promise<MedicalCompany> {
  return apiRequest<MedicalCompany>(withCompany('/api/v1/marketplace/company/store', company), { method: 'PATCH', body: payload })
}

export function setStoreActive(active: boolean, company?: string): Promise<MedicalCompany> {
  return apiRequest<MedicalCompany>(withCompany('/api/v1/marketplace/company/store/status', company), { method: 'POST', body: { active } })
}

export function listDocuments(company?: string, signal?: AbortSignal): Promise<SellerDocument[]> {
  return apiRequest<SellerDocument[]>(withCompany('/api/v1/marketplace/company/documents', company), { signal })
}

export function uploadDocument(kind: SellerDocumentKind, file: File, extra: { reference_number?: string; expires_on?: string } = {}, company?: string): Promise<SellerDocument> {
  const form = new FormData()
  form.append('kind', kind)
  form.append('file', file)
  if (extra.reference_number) form.append('reference_number', extra.reference_number)
  if (extra.expires_on) form.append('expires_on', extra.expires_on)
  return apiRequest<SellerDocument>(withCompany('/api/v1/marketplace/company/documents', company), { method: 'POST', body: form })
}

export function withdrawDocument(id: string, company?: string): Promise<void> {
  return apiRequest<void>(withCompany(`/api/v1/marketplace/company/documents/${enc(id)}`, company), { method: 'DELETE' })
}

/** Downloads a private file (document or photo) with the caller's credentials. */
export function fetchPrivateFile(url: string, company?: string): Promise<Blob> {
  return apiRequest<Blob>(withCompany(url, company), { responseType: 'blob' })
}

export function listShippingRates(company?: string, signal?: AbortSignal): Promise<ShippingRate[]> {
  return apiRequest<ShippingRate[]>(withCompany('/api/v1/marketplace/company/shipping-rates', company), { signal })
}

export function setShippingRate(body: { governorate: string; fee: string; min_days: number; max_days: number; is_active?: boolean }, company?: string): Promise<ShippingRate> {
  return apiRequest<ShippingRate>(withCompany('/api/v1/marketplace/company/shipping-rates', company), { method: 'POST', body })
}

export function deleteShippingRate(id: string, company?: string): Promise<void> {
  return apiRequest<void>(withCompany(`/api/v1/marketplace/company/shipping-rates/${enc(id)}`, company), { method: 'DELETE' })
}

export function listCompanyProducts(company?: string, page = 1, signal?: AbortSignal): Promise<PaginatedCompanyProducts> {
  return apiRequest<PaginatedCompanyProducts>(withCompany(`/api/v1/marketplace/company/products?page=${page}`, company), { signal })
}

export function createVariant(productId: string, body: VariantWrite, company?: string): Promise<OwnerVariant> {
  return apiRequest<OwnerVariant>(withCompany(`/api/v1/marketplace/company/products/${enc(productId)}/variants`, company), { method: 'POST', body })
}

export function updateVariant(id: string, body: VariantWrite, company?: string): Promise<OwnerVariant> {
  return apiRequest<OwnerVariant>(withCompany(`/api/v1/marketplace/company/variants/${enc(id)}`, company), { method: 'PATCH', body })
}

export function uploadProductPhoto(productId: string, file: File, altText = '', company?: string): Promise<ProductPhoto> {
  const form = new FormData()
  form.append('file', file)
  if (altText) form.append('alt_text', altText)
  return apiRequest<ProductPhoto>(withCompany(`/api/v1/marketplace/company/products/${enc(productId)}/images`, company), { method: 'POST', body: form })
}

export function deleteProductPhoto(id: string, company?: string): Promise<void> {
  return apiRequest<void>(withCompany(`/api/v1/marketplace/company/images/${enc(id)}`, company), { method: 'DELETE' })
}

export function updateCompanyProduct(id: string, payload: ProductWrite, company?: string): Promise<CompanyProduct> {
  return apiRequest<CompanyProduct>(withCompany(`/api/v1/marketplace/company/products/${enc(id)}`, company), { method: 'PATCH', body: payload })
}

// ---- administrators: seller documents --------------------------------------------------------
export function listSellerDocuments(status = 'PENDING', signal?: AbortSignal): Promise<{ results: SellerDocument[]; count: number }> {
  return apiRequest<{ results: SellerDocument[]; count: number }>(`/api/v1/admin/marketplace/documents?status=${enc(status)}`, { signal })
}

export function decideSellerDocument(id: string, approve: boolean, note = ''): Promise<SellerDocument> {
  return apiRequest<SellerDocument>(`/api/v1/admin/marketplace/documents/${enc(id)}/decision`, { method: 'POST', body: { approve, note } })
}

export interface AdminCompany extends MedicalCompany {
  account_email: string
}

export function listAdminCompanies(status = '', signal?: AbortSignal): Promise<{ results: AdminCompany[]; count: number }> {
  const query = status ? `?verification_status=${enc(status)}` : ''
  return apiRequest<{ results: AdminCompany[]; count: number }>(`/api/v1/admin/marketplace/companies${query}`, { signal })
}

export function decideCompanyVerification(id: string, status: 'VERIFIED' | 'REJECTED' | 'SUSPENDED' | 'UNVERIFIED', note = ''): Promise<AdminCompany> {
  return apiRequest<AdminCompany>(`/api/v1/admin/marketplace/companies/${enc(id)}/verification`, { method: 'POST', body: { status, note } })
}

export function listCompanyDocumentsAdmin(company: string, signal?: AbortSignal): Promise<{ results: SellerDocument[]; count: number }> {
  return apiRequest<{ results: SellerDocument[]; count: number }>(`/api/v1/admin/marketplace/documents?company=${enc(company)}`, { signal })
}
