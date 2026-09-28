import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as marketplaceApi from '../../api/endpoints/marketplace'
import * as referenceApi from '../../api/endpoints/reference'
import { tokenStore } from '../../api/tokens'
import type { CompanyDashboard, CompanyProduct, MarketplaceProduct, MedicalCompany, ProductCategory } from '../../api'
import { baghdad } from '../../test/providerFixtures'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/marketplace')
vi.mock('../../api/endpoints/reference')

const dental: ProductCategory = { id: 'cat-dental', slug: 'dental', name_ar: 'أجهزة الأسنان', name_en: 'Dental equipment', parent_id: null, sort_order: 0 }

function product(id: string, title: string, overrides: Partial<MarketplaceProduct> = {}): MarketplaceProduct {
  return {
    id,
    title,
    description: 'Sterilisable, CE marked.',
    brand: 'Acme',
    model_name: 'X1',
    price: '1500000.00',
    currency: 'IQD',
    category: dental,
    company: { id: 'co-1', name: 'Dental Supply Co', governorate: baghdad, city: null, website: '', public_email: '', phone: '' },
    created_at: '2026-09-28T00:00:00Z',
    updated_at: '2026-09-28T00:00:00Z',
    ...overrides,
  }
}

const page = (results: MarketplaceProduct[], count = results.length, next: string | null = null, previous: string | null = null) => ({ count, next, previous, results })

function company(overrides: Partial<MedicalCompany> = {}): MedicalCompany {
  return {
    id: 'co-1',
    name: 'Dental Supply Co',
    description: '',
    phone: '',
    public_email: '',
    website: '',
    governorate: baghdad,
    city: null,
    address: '',
    verification_status: 'VERIFIED',
    verification_note: '',
    verification_requested_at: null,
    verification_changed_at: null,
    verified_at: '2026-09-28T00:00:00Z',
    can_publish: true,
    created_at: '2026-09-28T00:00:00Z',
    updated_at: '2026-09-28T00:00:00Z',
    ...overrides,
  }
}

function ownProduct(id: string, title: string, is_active: boolean): CompanyProduct {
  const { company: _c, ...rest } = product(id, title)
  return { ...rest, is_active }
}

const dashboard: CompanyDashboard = {
  verification_status: 'VERIFIED',
  can_publish: true,
  products_total: 3,
  products_active: 2,
  products_inactive: 1,
  products_exposable: 2,
}

describe('Provider marketplace', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PROVIDER' }))
    vi.mocked(marketplaceApi.listCategories).mockResolvedValue([dental])
  })

  it('shows loading then exactly the products the backend targeted', async () => {
    const pending = deferred<ReturnType<typeof page>>()
    vi.mocked(marketplaceApi.listTargetedProducts).mockReturnValue(pending.promise)
    renderApp('/marketplace')
    expect(await screen.findByTestId('marketplace-loading')).toBeInTheDocument()
    pending.resolve(page([product('p-1', 'Dental chair', { price: null })]))
    const rows = await screen.findAllByTestId('marketplace-product')
    expect(rows).toHaveLength(1) // nothing added or removed on the client
    expect(within(rows[0]!).getByRole('link', { name: 'Dental chair' })).toHaveAttribute('href', '/marketplace/products/p-1')
    expect(within(rows[0]!).getByText(/السعر عند الطلب|price on request/i)).toBeInTheDocument()
    expect(marketplaceApi.listTargetedProducts).toHaveBeenCalledWith(1, '', expect.anything())
  })

  it('paginates through the backend and passes the category filter through', async () => {
    vi.mocked(marketplaceApi.listTargetedProducts).mockImplementation(async (p = 1) =>
      p === 1
        ? page(Array.from({ length: 20 }, (_, i) => product(`p-${i}`, `Item ${i}`)), 21, 'next')
        : page([product('p-20', 'Item 20')], 21, null, 'prev'),
    )
    renderApp('/marketplace')
    expect(await screen.findByText('Item 0')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /التالي|next/i }))
    expect(await screen.findByText('Item 20')).toBeInTheDocument()
    expect(marketplaceApi.listTargetedProducts).toHaveBeenCalledWith(2, '', expect.anything())
    await userEvent.selectOptions(screen.getByLabelText(/الفئة|category/i), 'cat-dental')
    await waitFor(() => expect(marketplaceApi.listTargetedProducts).toHaveBeenCalledWith(1, 'cat-dental', expect.anything()))
  })

  it('shows the empty and error states', async () => {
    vi.mocked(marketplaceApi.listTargetedProducts).mockResolvedValue(page([]))
    renderApp('/marketplace')
    expect(await screen.findByTestId('marketplace-empty')).toBeInTheDocument()
    vi.mocked(marketplaceApi.listTargetedProducts).mockRejectedValue(new ApiError(403, 'permission_denied', 'A verified provider profile is required.'))
    renderApp('/marketplace')
    expect((await screen.findAllByRole('alert')).length).toBeGreaterThan(0)
  })

  it('renders a targeted product detail and a non-disclosing 404', async () => {
    vi.mocked(marketplaceApi.getTargetedProduct).mockResolvedValue(product('p-1', 'Dental chair'))
    renderApp('/marketplace/products/p-1')
    expect(await screen.findByRole('heading', { name: 'Dental chair' })).toBeInTheDocument()
    expect(screen.getByText('Dental Supply Co')).toBeInTheDocument()
    vi.mocked(marketplaceApi.getTargetedProduct).mockRejectedValue(new ApiError(404, 'not_found', 'Not found.'))
    renderApp('/marketplace/products/other')
    expect(await screen.findByText(/غير متاح لك|not available to you/i)).toBeInTheDocument()
  })

  it('keeps the marketplace for providers only', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PATIENT' }))
    renderApp('/marketplace')
    expect(await screen.findByTestId('role-denied')).toBeInTheDocument()
    expect(marketplaceApi.listTargetedProducts).not.toHaveBeenCalled()
  })
})

describe('Company workspace', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'MEDICAL_COMPANY' }))
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad])
    vi.mocked(marketplaceApi.listCategories).mockResolvedValue([dental])
    vi.mocked(marketplaceApi.getCompanyDashboard).mockResolvedValue(dashboard)
    vi.mocked(marketplaceApi.listMyProducts).mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [ownProduct('d-1', 'Draft chair', false), ownProduct('a-1', 'Live chair', true)],
    })
  })

  it('onboards a company that has no profile yet', async () => {
    vi.mocked(marketplaceApi.getMyCompany).mockRejectedValue(new ApiError(404, 'not_found', 'none'))
    vi.mocked(marketplaceApi.createMyCompany).mockResolvedValue(company({ verification_status: 'UNVERIFIED', can_publish: false }))
    renderApp('/company')
    const form = await screen.findByTestId('company-onboarding')
    const user = userEvent.setup()
    await user.click(within(form).getByRole('button', { name: /إنشاء ملف الشركة|create company profile/i }))
    expect(marketplaceApi.createMyCompany).not.toHaveBeenCalled() // client validation first
    await user.type(within(form).getByLabelText(/اسم الشركة|company name/i), 'Dental Supply Co')
    await user.selectOptions(within(form).getByLabelText(/المحافظة|governorate/i), baghdad.id)
    await user.click(within(form).getByRole('button', { name: /إنشاء ملف الشركة|create company profile/i }))
    await waitFor(() => expect(marketplaceApi.createMyCompany).toHaveBeenCalledWith(expect.objectContaining({ name: 'Dental Supply Co', governorate: baghdad.id })))
  })

  it('shows the backend dashboard and verification state, and requests verification', async () => {
    vi.mocked(marketplaceApi.getMyCompany).mockResolvedValue(company({ verification_status: 'UNVERIFIED', can_publish: false }))
    vi.mocked(marketplaceApi.getCompanyDashboard).mockResolvedValue({ ...dashboard, verification_status: 'UNVERIFIED', can_publish: false, products_exposable: 0 })
    vi.mocked(marketplaceApi.requestCompanyVerification).mockResolvedValue(company({ verification_status: 'PENDING', can_publish: false }))
    renderApp('/company')
    expect(await screen.findByTestId('stat-total')).toHaveTextContent('3')
    expect(screen.getByTestId('stat-exposable')).toHaveTextContent('0')
    expect(screen.getByTestId('company-verification-state')).toHaveTextContent(/غير موثّقة|not verified/i)
    // an unverified company is never offered Publish (the backend would refuse it)
    expect(screen.queryByRole('button', { name: /^نشر$|^publish$/i })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /طلب التوثيق|request verification/i }))
    await waitFor(() => expect(marketplaceApi.requestCompanyVerification).toHaveBeenCalledTimes(1))
  })

  it('hides the verification request once pending', async () => {
    vi.mocked(marketplaceApi.getMyCompany).mockResolvedValue(company({ verification_status: 'PENDING', can_publish: false }))
    renderApp('/company')
    expect(await screen.findByTestId('company-verification-state')).toHaveTextContent(/قيد المراجعة|being reviewed/i)
    expect(screen.queryByRole('button', { name: /طلب التوثيق|request verification/i })).toBeNull()
  })

  it('creates, edits, publishes and unpublishes products', async () => {
    vi.mocked(marketplaceApi.getMyCompany).mockResolvedValue(company())
    vi.mocked(marketplaceApi.createMyProduct).mockResolvedValue(ownProduct('n-1', 'New scaler', false))
    vi.mocked(marketplaceApi.updateMyProduct).mockResolvedValue(ownProduct('d-1', 'Draft chair v2', false))
    vi.mocked(marketplaceApi.setMyProductActive).mockImplementation(async (id, active) => ownProduct(id, 'x', active))
    renderApp('/company')
    const user = userEvent.setup()
    const form = await screen.findByTestId('product-form')
    await user.selectOptions(within(form).getByLabelText(/الفئة|category/i), 'cat-dental')
    await user.type(within(form).getByLabelText(/اسم المنتج|product name/i), 'New scaler')
    await user.type(within(form).getByLabelText(/السعر|price/i), '-5')
    await user.click(within(form).getByRole('button', { name: /إنشاء المنتج|create product/i }))
    expect(marketplaceApi.createMyProduct).not.toHaveBeenCalled() // negative price refused client-side
    await user.clear(within(form).getByLabelText(/السعر|price/i))
    await user.click(within(form).getByRole('button', { name: /إنشاء المنتج|create product/i }))
    await waitFor(() => expect(marketplaceApi.createMyProduct).toHaveBeenCalledWith(expect.objectContaining({ category: 'cat-dental', title: 'New scaler', price: null })))
    // the payload never carries targeting fields
    expect(Object.keys(vi.mocked(marketplaceApi.createMyProduct).mock.calls[0]![0])).not.toEqual(expect.arrayContaining(['provider_type', 'specialty', 'audience', 'is_active']))

    const rows = await screen.findAllByTestId('company-product')
    await user.click(within(rows[0]!).getByRole('button', { name: /^نشر$|^publish$/i }))
    await waitFor(() => expect(marketplaceApi.setMyProductActive).toHaveBeenCalledWith('d-1', true))
    await user.click(within(rows[1]!).getByRole('button', { name: /إلغاء النشر|unpublish/i }))
    await waitFor(() => expect(marketplaceApi.setMyProductActive).toHaveBeenCalledWith('a-1', false))

    await user.click(within(rows[0]!).getByRole('button', { name: /تعديل|edit/i }))
    const editForm = await screen.findByTestId('product-form')
    const titleField = within(editForm).getByLabelText(/اسم المنتج|product name/i)
    expect(titleField).toHaveValue('Draft chair')
    await user.clear(titleField)
    await user.type(titleField, 'Draft chair v2')
    await user.click(within(editForm).getByRole('button', { name: /حفظ المنتج|save product/i }))
    await waitFor(() => expect(marketplaceApi.updateMyProduct).toHaveBeenCalledWith('d-1', expect.objectContaining({ title: 'Draft chair v2' })))
  })

  it('paginates own products through the backend', async () => {
    vi.mocked(marketplaceApi.getMyCompany).mockResolvedValue(company())
    vi.mocked(marketplaceApi.listMyProducts).mockImplementation(async (p = 1) => ({
      count: 21,
      next: p === 1 ? 'n' : null,
      previous: p === 1 ? null : 'p',
      results: p === 1 ? Array.from({ length: 20 }, (_, i) => ownProduct(`o-${i}`, `Own ${i}`, false)) : [ownProduct('o-20', 'Own 20', false)],
    }))
    renderApp('/company')
    expect(await screen.findByText('Own 0')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /التالي|next/i }))
    expect(await screen.findByText('Own 20')).toBeInTheDocument()
    expect(marketplaceApi.listMyProducts).toHaveBeenCalledWith(2, expect.anything())
  })

  it('keeps the workspace for medical company accounts only', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PROVIDER' }))
    renderApp('/company')
    expect(await screen.findByTestId('role-denied')).toHaveTextContent(/الشركات الطبية|medical company accounts/i)
    expect(marketplaceApi.getMyCompany).not.toHaveBeenCalled()
  })
})
