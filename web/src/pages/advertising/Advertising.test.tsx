import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as advertisingApi from '../../api/endpoints/advertising'
import * as authApi from '../../api/endpoints/auth'
import * as marketplaceApi from '../../api/endpoints/marketplace'
import * as referenceApi from '../../api/endpoints/reference'
import { tokenStore } from '../../api/tokens'
import type { AdminCampaign, Campaign, CampaignDashboard, CompanyProduct, MarketplaceProduct, MedicalCompany, ProductCategory, SponsoredCampaign, Specialty } from '../../api'
import i18n from '../../i18n'
import { baghdad, basra } from '../../test/providerFixtures'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

// These pages chain several backend loads; be generous so a slow or busy machine does not flake (per test file).
configure({ asyncUtilTimeout: 5000 })

vi.mock('../../api/endpoints/advertising')
vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/marketplace')
vi.mock('../../api/endpoints/reference')

const page = <T,>(results: T[], count = results.length, next: string | null = null, previous: string | null = null) => ({ count, next, previous, results })

const dental: ProductCategory = { id: 'cat-dental', slug: 'dental', name_ar: 'أجهزة الأسنان', name_en: 'Dental equipment', parent_id: null, sort_order: 0, can_publish: true }
const dentistry: Specialty = { id: 'sp-dent', slug: 'dentistry', name_ar: 'طب الأسنان', name_en: 'Dentistry', parent: null }
const cardiology: Specialty = { id: 'sp-card', slug: 'cardiology', name_ar: 'أمراض القلب', name_en: 'Cardiology', parent: null }

function companyProduct(id: string, title: string, is_active = true): CompanyProduct {
  return { id, title, description: '', brand: '', model_name: '', price: '1000', currency: 'IQD', category: dental, is_active, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z' }
}

const company: MedicalCompany = {
  id: 'co-1', name: 'Dental Supply Co', description: '', phone: '', public_email: '', website: '', governorate: baghdad, city: null, address: '',
  verification_status: 'VERIFIED', verification_note: '', verification_requested_at: null, verification_changed_at: null, verified_at: null,
  can_publish: true, identity_locked: true, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z',
}

function campaign(id: string, name: string, overrides: Partial<Campaign> = {}): Campaign {
  return {
    id,
    name,
    product: { id: 'p-1', title: 'Dental chair', brand: '', model_name: '', is_active: true, category: { id: 'cat-dental', slug: 'dental', name_ar: 'أجهزة الأسنان', name_en: 'Dental equipment' } },
    starts_on: '2030-01-01',
    ends_on: '2030-01-10',
    status: 'DRAFT',
    provider_types: [],
    specialties: [],
    governorates: [],
    quote: null,
    payment: null,
    is_live: false,
    is_ended: false,
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
    ...overrides,
  }
}

const QUOTE = { days: 10, daily_rate: '1000.00', amount: '10000.00', currency: 'IQD', quoted_at: '2026-10-01T00:00:00Z' }
const pendingPayment = { status: 'PENDING', amount: '10000.00', currency: 'IQD', method: '', reference: '', created_at: '2026-10-01T00:00:00Z', verified_at: null } as const

const dashboard: CampaignDashboard = {
  campaigns_total: 9,
  campaigns_draft: 2,
  campaigns_pending_payment: 1,
  campaigns_active: 3,
  campaigns_live: 2,
  campaigns_ended: 1,
  campaigns_rejected: 1,
  campaigns_cancelled: 1,
}

function setupCompany() {
  tokenStore.set({ access: 'a', refresh: 'r' })
  vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'MEDICAL_COMPANY' }))
  vi.mocked(marketplaceApi.getMyCompany).mockResolvedValue(company)
  vi.mocked(marketplaceApi.listMyProducts).mockResolvedValue(page([companyProduct('p-1', 'Dental chair'), companyProduct('p-2', 'Sterilizer'), companyProduct('p-3', 'Unpublished lamp', false)]))
  vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad, basra])
  vi.mocked(referenceApi.listSpecialties).mockResolvedValue([dentistry, cardiology])
  vi.mocked(advertisingApi.getCampaignDashboard).mockResolvedValue(dashboard)
  vi.mocked(advertisingApi.listMyCampaigns).mockResolvedValue(page([]))
  vi.mocked(advertisingApi.quoteCampaign).mockResolvedValue({ days: 10, daily_rate: '1000.00', total: '10000.00', currency: 'IQD' })
}

const SUBMIT = /إرسال للتحقق من الدفع|submit for payment verification/i
const CANCEL_CAMPAIGN = /إلغاء الحملة|cancel campaign/i
const EDIT = /^تعديل$|^edit$/i

describe('Company advertising access', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
  })

  it.each(['PATIENT', 'PROVIDER', 'REAL_ESTATE_SELLER'] as const)('keeps the page away from %s accounts', async (role) => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role }))
    renderApp('/company/advertising')
    expect(await screen.findByTestId('role-denied')).toBeInTheDocument()
    expect(marketplaceApi.getMyCompany).not.toHaveBeenCalled()
    expect(advertisingApi.getCampaignDashboard).not.toHaveBeenCalled()
  })

  it('sends an anonymous visitor to log in', async () => {
    tokenStore.clear()
    const { router } = renderApp('/company/advertising')
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
  })

  it('asks a company without a profile to create one first', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'MEDICAL_COMPANY' }))
    vi.mocked(marketplaceApi.getMyCompany).mockRejectedValue(new ApiError(404, 'not_found', 'none'))
    renderApp('/company/advertising')
    expect(await screen.findByTestId('advertising-no-company')).toBeInTheDocument()
    expect(advertisingApi.getCampaignDashboard).not.toHaveBeenCalled()
  })

  it('is reachable from the company workspace and the header', async () => {
    setupCompany()
    vi.mocked(marketplaceApi.getCompanyDashboard).mockResolvedValue({ verification_status: 'VERIFIED', can_publish: true, products_total: 0, products_active: 0, products_inactive: 0, products_exposable: 0 })
    vi.mocked(marketplaceApi.listCategories).mockResolvedValue([dental])
    vi.mocked(marketplaceApi.listMyProducts).mockResolvedValue(page([]))
    renderApp('/company')
    await screen.findByTestId('company-dashboard')
    const hrefs = screen.getAllByRole('link').map((a) => a.getAttribute('href'))
    expect(hrefs).toContain('/company/advertising')
  })
})

describe('Company advertising workspace', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    setupCompany()
  })

  it('shows the dashboard loading, error with retry, and the backend counts', async () => {
    const pending = deferred<CampaignDashboard>()
    vi.mocked(advertisingApi.getCampaignDashboard).mockReturnValueOnce(pending.promise)
    renderApp('/company/advertising')
    expect(await screen.findByTestId('advertising-dashboard-loading')).toBeInTheDocument()
    pending.reject(new ApiError(500, 'server_error', 'Boom.'))
    const retry = await screen.findByRole('button', { name: /إعادة المحاولة|try again|retry/i })
    await userEvent.click(retry)
    expect(await screen.findByTestId('advertising-dashboard')).toBeInTheDocument()
    expect(screen.getByTestId('stat-total')).toHaveTextContent('9')
    expect(screen.getByTestId('stat-draft')).toHaveTextContent('2')
    expect(screen.getByTestId('stat-pending')).toHaveTextContent('1')
    expect(screen.getByTestId('stat-active')).toHaveTextContent('3')
    expect(screen.getByTestId('stat-live')).toHaveTextContent('2')
    expect(screen.getByTestId('stat-ended')).toHaveTextContent('1')
    expect(screen.getByTestId('stat-rejected')).toHaveTextContent('1')
    expect(screen.getByTestId('stat-cancelled')).toHaveTextContent('1')
  })

  it('shows the empty state and the campaign-list error', async () => {
    renderApp('/company/advertising')
    expect(await screen.findByTestId('advertising-campaigns-empty')).toBeInTheDocument()
    vi.mocked(advertisingApi.listMyCampaigns).mockRejectedValue(new ApiError(500, 'server_error', 'Boom.'))
    renderApp('/company/advertising')
    expect((await screen.findAllByRole('alert')).length).toBeGreaterThan(0)
  })

  it('offers only the company\'s own products (from the existing company API), inactive ones marked', async () => {
    renderApp('/company/advertising')
    const form = await screen.findByTestId('campaign-form')
    const select = within(form).getByLabelText(/^المنتج|^product/i)
    const names = within(select).getAllByRole('option').map((o) => o.textContent)
    expect(names.join('|')).toMatch(/Dental chair/)
    expect(names.join('|')).toMatch(/Sterilizer/)
    expect(names.join('|')).toMatch(/Unpublished lamp \((غير منشور|not published)\)/)
    expect(marketplaceApi.listMyProducts).toHaveBeenCalled()
  })

  it('creates a draft with only owner-editable data and structured targeting', async () => {
    vi.mocked(advertisingApi.createCampaign).mockResolvedValue(campaign('c-new', 'Spring push'))
    renderApp('/company/advertising')
    const user = userEvent.setup()
    const form = await screen.findByTestId('campaign-form')
    await user.click(within(form).getByRole('button', { name: /حفظ المسودة|save draft/i }))
    expect(advertisingApi.createCampaign).not.toHaveBeenCalled() // name and product are required
    await user.type(within(form).getByLabelText(/اسم الحملة|campaign name/i), 'Spring push')
    await user.selectOptions(within(form).getByLabelText(/^المنتج|^product/i), 'p-1')
    await user.type(within(form).getByLabelText(/تاريخ البدء|start date/i), '2030-01-01')
    await user.type(within(form).getByLabelText(/تاريخ الانتهاء|end date/i), '2030-01-10')
    await user.click(within(form).getByRole('checkbox', { name: /طبيب|doctor/i }))
    await user.click(within(form).getByRole('checkbox', { name: /طب الأسنان|dentistry/i }))
    await user.click(within(form).getByRole('checkbox', { name: /بغداد|baghdad/i }))
    await user.click(within(form).getByRole('button', { name: /حفظ المسودة|save draft/i }))
    await waitFor(() => expect(advertisingApi.createCampaign).toHaveBeenCalled())
    const payload = vi.mocked(advertisingApi.createCampaign).mock.calls[0]![0]
    expect(payload).toEqual({ name: 'Spring push', product: 'p-1', starts_on: '2030-01-01', ends_on: '2030-01-10', provider_types: ['DOCTOR'], specialties: ['sp-dent'], governorates: ['g-baghdad'] })
    // nothing commercial or lifecycle can leave the browser
    for (const forbidden of ['status', 'amount', 'quoted_amount', 'price', 'total', 'currency', 'payment_status', 'is_paid', 'company', 'quote']) {
      expect(payload).not.toHaveProperty(forbidden)
    }
  })

  it('has no input for an amount, payment, status or "paid"', async () => {
    renderApp('/company/advertising')
    const form = await screen.findByTestId('campaign-form')
    for (const pattern of [/المبلغ|amount/i, /السعر|^price/i, /مدفوع|paid/i, /الحالة|^status/i, /تحقق|verified/i]) {
      expect(within(form).queryByLabelText(pattern)).toBeNull()
    }
    expect(within(form).queryAllByRole('combobox').map((s) => s.getAttribute('name'))).not.toContain('status')
  })

  it('refuses a missing name/product and an end date before the start date, client-side', async () => {
    renderApp('/company/advertising')
    const user = userEvent.setup()
    const form = await screen.findByTestId('campaign-form')
    await user.type(within(form).getByLabelText(/اسم الحملة|campaign name/i), 'X')
    await user.selectOptions(within(form).getByLabelText(/^المنتج|^product/i), 'p-1')
    await user.type(within(form).getByLabelText(/تاريخ البدء|start date/i), '2030-01-10')
    await user.type(within(form).getByLabelText(/تاريخ الانتهاء|end date/i), '2030-01-01')
    await user.click(within(form).getByRole('button', { name: /حفظ المسودة|save draft/i }))
    expect(advertisingApi.createCampaign).not.toHaveBeenCalled()
    expect(within(form).getByText(/لا يمكن أن يسبق تاريخ الانتهاء|end date cannot be before/i)).toBeInTheDocument()
  })

  it('shows backend validation errors on the form fields', async () => {
    vi.mocked(advertisingApi.createCampaign).mockRejectedValue(new ApiError(400, 'validation_error', 'Validation failed.', { governorates: ['x'] }, { governorates: ['governorate_inactive'] }))
    renderApp('/company/advertising')
    const user = userEvent.setup()
    const form = await screen.findByTestId('campaign-form')
    await user.type(within(form).getByLabelText(/اسم الحملة|campaign name/i), 'X')
    await user.selectOptions(within(form).getByLabelText(/^المنتج|^product/i), 'p-1')
    await user.click(within(form).getByRole('button', { name: /حفظ المسودة|save draft/i }))
    expect(await within(form).findByText(/لم تعد متاحة|no longer available/i)).toBeInTheDocument()
  })

  describe('quote preview', () => {
    it('asks the backend only for a valid date range and shows the current backend quote', async () => {
      vi.mocked(advertisingApi.quoteCampaign).mockResolvedValue({ days: 10, daily_rate: '1000.00', total: '10000.00', currency: 'IQD' })
      renderApp('/company/advertising')
      const user = userEvent.setup()
      const form = await screen.findByTestId('campaign-form')
      expect(advertisingApi.quoteCampaign).not.toHaveBeenCalled()
      await user.type(within(form).getByLabelText(/تاريخ البدء|start date/i), '2030-01-01')
      expect(advertisingApi.quoteCampaign).not.toHaveBeenCalled() // one date is not a range
      await user.type(within(form).getByLabelText(/تاريخ الانتهاء|end date/i), '2030-01-10')
      const preview = await screen.findByTestId('quote-preview')
      await waitFor(() => expect(advertisingApi.quoteCampaign).toHaveBeenCalledWith({ starts_on: '2030-01-01', ends_on: '2030-01-10' }, expect.anything()))
      expect(await within(preview).findByTestId('quote-days')).toHaveTextContent('10')
      expect(within(preview).getByTestId('quote-rate')).toHaveTextContent(/1,000|١٬٠٠٠|1000/)
      expect(within(preview).getByTestId('quote-total')).toHaveTextContent(/10,000|١٠٬٠٠٠|10000/)
      expect(within(preview).getByTestId('quote-total')).toHaveTextContent('IQD')
      expect(within(preview).getByText(/السعر الحالي من الخادم|current backend quote/i)).toBeInTheDocument()
    })

    it('says pricing has not been configured and invents nothing', async () => {
      vi.mocked(advertisingApi.quoteCampaign).mockRejectedValue(new ApiError(409, 'pricing_unavailable', 'No price.'))
      renderApp('/company/advertising')
      const user = userEvent.setup()
      const form = await screen.findByTestId('campaign-form')
      await user.type(within(form).getByLabelText(/تاريخ البدء|start date/i), '2030-01-01')
      await user.type(within(form).getByLabelText(/تاريخ الانتهاء|end date/i), '2030-01-10')
      expect(await screen.findByTestId('pricing-unavailable')).toHaveTextContent(/لم تُحدِّد رشيتة أسعار|has not been configured/i)
      expect(screen.queryByTestId('quote-total')).toBeNull()
      expect(screen.queryByTestId('quote-rate')).toBeNull()
    })

    it('never sends the previewed price back when saving the draft', async () => {
      vi.mocked(advertisingApi.quoteCampaign).mockResolvedValue({ days: 10, daily_rate: '1000.00', total: '10000.00', currency: 'IQD' })
      vi.mocked(advertisingApi.createCampaign).mockResolvedValue(campaign('c-new', 'X'))
      renderApp('/company/advertising')
      const user = userEvent.setup()
      const form = await screen.findByTestId('campaign-form')
      await user.type(within(form).getByLabelText(/اسم الحملة|campaign name/i), 'X')
      await user.selectOptions(within(form).getByLabelText(/^المنتج|^product/i), 'p-1')
      await user.type(within(form).getByLabelText(/تاريخ البدء|start date/i), '2030-01-01')
      await user.type(within(form).getByLabelText(/تاريخ الانتهاء|end date/i), '2030-01-10')
      await screen.findByTestId('quote-total')
      await user.click(within(form).getByRole('button', { name: /حفظ المسودة|save draft/i }))
      await waitFor(() => expect(advertisingApi.createCampaign).toHaveBeenCalled())
      expect(JSON.stringify(vi.mocked(advertisingApi.createCampaign).mock.calls[0]![0])).not.toMatch(/10000|1000\.00|"(total|daily_rate|amount|price|currency|quote)"/)
    })
  })

  describe('campaign lifecycle', () => {
    it('submits a draft without sending any price and then shows the backend snapshot and the pending-payment state', async () => {
      vi.mocked(advertisingApi.listMyCampaigns)
        .mockResolvedValueOnce(page([campaign('c-1', 'Spring push')]))
        .mockResolvedValue(page([campaign('c-1', 'Spring push', { status: 'PENDING_PAYMENT', quote: QUOTE, payment: pendingPayment })]))
      vi.mocked(advertisingApi.submitCampaign).mockResolvedValue(campaign('c-1', 'Spring push', { status: 'PENDING_PAYMENT', quote: QUOTE, payment: pendingPayment }))
      renderApp('/company/advertising')
      const user = userEvent.setup()
      const row = (await screen.findAllByTestId('campaign'))[0]!
      await user.click(within(row).getByRole('button', { name: SUBMIT }))
      await waitFor(() => expect(advertisingApi.submitCampaign).toHaveBeenCalledWith('c-1'))
      expect(vi.mocked(advertisingApi.submitCampaign).mock.calls[0]).toHaveLength(1) // the id only: no amount, no quote
      const pending = await screen.findByTestId('pending-title')
      expect(pending).toHaveTextContent(/بانتظار التحقق من الدفع|pending payment verification/i)
      const after = screen.getAllByTestId('campaign')[0]!
      expect(within(after).getByText(/خارج المنصة|outside the platform/i)).toBeInTheDocument()
      expect(within(after).getByText(/لا تصبح الحملة نشطة|never becomes active/i)).toBeInTheDocument()
      expect(within(after).getByTestId('campaign-quote')).toHaveTextContent(/10.*1,000|١٠.*١٬٠٠٠|10 .*1000/)
      expect(within(after).getByTestId('campaign-quote')).toHaveTextContent(/10,000|١٠٬٠٠٠|10000/)
      expect(within(after).getByTestId('campaign-payment')).toHaveTextContent(/قيد الانتظار|pending/i)
      expect(within(after).queryByRole('button', { name: SUBMIT })).toBeNull()
      expect(within(after).queryByRole('button', { name: EDIT })).toBeNull() // frozen once submitted
      expect(screen.queryByText(/QR|IBAN|رقم الحساب/i)).toBeNull() // no fake bank details or provider
    })

    it('offers Edit and Submit only for drafts that can be submitted, and explains what is missing', async () => {
      vi.mocked(advertisingApi.listMyCampaigns).mockResolvedValue(
        page([
          campaign('ok', 'Ready'),
          campaign('nodates', 'No dates', { starts_on: null, ends_on: null }),
          campaign('inactive', 'Product off', { product: { ...campaign('x', 'x').product, is_active: false } }),
        ]),
      )
      renderApp('/company/advertising')
      const rows = await screen.findAllByTestId('campaign')
      expect(within(rows[0]!).getByRole('button', { name: SUBMIT })).toBeInTheDocument()
      for (const i of [1, 2]) {
        expect(within(rows[i]!).queryByRole('button', { name: SUBMIT })).toBeNull()
        expect(within(rows[i]!).getByTestId('submit-hint')).toBeInTheDocument()
        expect(within(rows[i]!).getByRole('button', { name: EDIT })).toBeInTheDocument()
      }
    })

    it('edits only drafts: pending, active, rejected and cancelled campaigns have no Edit', async () => {
      vi.mocked(advertisingApi.listMyCampaigns).mockResolvedValue(
        page([
          campaign('p', 'Pending', { status: 'PENDING_PAYMENT', quote: QUOTE, payment: pendingPayment }),
          campaign('a', 'Active', { status: 'ACTIVE', quote: QUOTE, is_live: true }),
          campaign('r', 'Rejected', { status: 'REJECTED', quote: QUOTE }),
          campaign('c', 'Cancelled', { status: 'CANCELLED', quote: QUOTE }),
        ]),
      )
      renderApp('/company/advertising')
      const rows = await screen.findAllByTestId('campaign')
      for (const row of rows) expect(within(row).queryByRole('button', { name: EDIT })).toBeNull()
    })

    it('loads a draft into the form, saves it through the update endpoint and leaves edit mode', async () => {
      vi.mocked(advertisingApi.listMyCampaigns).mockResolvedValue(page([campaign('c-1', 'Old name', { provider_types: ['DOCTOR'], governorates: [{ ...baghdad, is_active: true }] })]))
      vi.mocked(advertisingApi.updateCampaign).mockResolvedValue(campaign('c-1', 'New name'))
      renderApp('/company/advertising')
      const user = userEvent.setup()
      const row = (await screen.findAllByTestId('campaign'))[0]!
      await user.click(within(row).getByRole('button', { name: EDIT }))
      const form = await screen.findByTestId('campaign-form')
      const name = within(form).getByLabelText(/اسم الحملة|campaign name/i)
      expect(name).toHaveValue('Old name')
      expect(within(form).getByRole('checkbox', { name: /طبيب|doctor/i })).toBeChecked()
      await user.clear(name)
      await user.type(name, 'New name')
      await user.click(within(form).getByRole('button', { name: /حفظ التعديلات|save changes/i }))
      await waitFor(() => expect(advertisingApi.updateCampaign).toHaveBeenCalledWith('c-1', expect.objectContaining({ name: 'New name', provider_types: ['DOCTOR'], governorates: ['g-baghdad'] })))
    })

    it('keeps a saved target that is no longer active visible so it can be unchecked', async () => {
      const gone = { id: 'g-gone', slug: 'gone', name_ar: 'محافظة قديمة', name_en: 'Old governorate', is_active: false }
      vi.mocked(advertisingApi.listMyCampaigns).mockResolvedValue(page([campaign('c-1', 'X', { governorates: [gone] })]))
      vi.mocked(advertisingApi.updateCampaign).mockResolvedValue(campaign('c-1', 'X'))
      renderApp('/company/advertising')
      const user = userEvent.setup()
      const row = (await screen.findAllByTestId('campaign'))[0]!
      await user.click(within(row).getByRole('button', { name: EDIT }))
      const form = await screen.findByTestId('campaign-form')
      const stale = within(form).getByRole('checkbox', { name: /محافظة قديمة|Old governorate/ })
      expect(stale).toBeChecked()
      expect(stale.closest('label')).toHaveTextContent(/لم تعد متاحة|no longer available/)
      await user.click(stale) // uncheck to recover
      await user.click(within(form).getByRole('button', { name: /حفظ التعديلات|save changes/i }))
      await waitFor(() => expect(advertisingApi.updateCampaign).toHaveBeenCalled())
      expect(vi.mocked(advertisingApi.updateCampaign).mock.calls[0]![1]).toMatchObject({ governorates: [] })
    })

    it('cancels an active campaign through the backend and ignores a second click while busy', async () => {
      vi.mocked(advertisingApi.listMyCampaigns).mockResolvedValue(page([campaign('a-1', 'Active', { status: 'ACTIVE', quote: QUOTE, is_live: true })]))
      const pending = deferred<Campaign>()
      vi.mocked(advertisingApi.cancelCampaign).mockReturnValue(pending.promise)
      renderApp('/company/advertising')
      const user = userEvent.setup()
      const row = (await screen.findAllByTestId('campaign'))[0]!
      expect(within(row).getByText(/جارية|^live$/i)).toBeInTheDocument()
      await user.click(within(row).getByRole('button', { name: CANCEL_CAMPAIGN }))
      await waitFor(() => expect(within(row).getByRole('button', { name: /جارٍ الإلغاء|cancelling/i })).toBeDisabled())
      await user.click(within(row).getByRole('button', { name: /جارٍ الإلغاء|cancelling/i }))
      expect(advertisingApi.cancelCampaign).toHaveBeenCalledTimes(1)
      expect(advertisingApi.cancelCampaign).toHaveBeenCalledWith('a-1')
      pending.resolve(campaign('a-1', 'Active', { status: 'CANCELLED' }))
    })

    it('shows rejected, cancelled and ended states without offering actions', async () => {
      vi.mocked(advertisingApi.listMyCampaigns).mockResolvedValue(
        page([
          campaign('r', 'Rejected', { status: 'REJECTED', quote: QUOTE, payment: { ...pendingPayment, status: 'REJECTED' } }),
          campaign('c', 'Cancelled', { status: 'CANCELLED', quote: QUOTE }),
          campaign('e', 'Ended', { status: 'ACTIVE', quote: QUOTE, is_ended: true }),
        ]),
      )
      renderApp('/company/advertising')
      const [rejected, cancelled, ended] = await screen.findAllByTestId('campaign')
      expect(within(rejected!).getByText(/رُفض الدفع|payment was rejected/i)).toBeInTheDocument()
      expect(within(rejected!).queryAllByRole('button')).toHaveLength(0)
      expect(within(cancelled!).getByText(/أُلغيت هذه الحملة|was cancelled/i)).toBeInTheDocument()
      expect(within(ended!).getByText(/تجاوزت هذه الحملة|passed its end date/i)).toBeInTheDocument()
    })

    it('shows every typed backend reason when submission is refused', async () => {
      vi.mocked(advertisingApi.listMyCampaigns).mockResolvedValue(page([campaign('c-1', 'X')]))
      vi.mocked(advertisingApi.submitCampaign).mockRejectedValue(new ApiError(409, 'pricing_unavailable', 'No price.'))
      renderApp('/company/advertising')
      const user = userEvent.setup()
      const row = (await screen.findAllByTestId('campaign'))[0]!
      await user.click(within(row).getByRole('button', { name: SUBMIT }))
      expect(await screen.findByRole('alert')).toHaveTextContent(/لم تُحدِّد رشيتة أسعار|has not been configured/i)
      vi.mocked(advertisingApi.submitCampaign).mockRejectedValue(
        new ApiError(400, 'validation_error', 'Validation failed.', { ends_on: ['x'], governorates: ['y'] }, { ends_on: ['end_in_past'], governorates: ['governorate_inactive'] }),
      )
      await user.click(within(row).getByRole('button', { name: SUBMIT }))
      await waitFor(() => {
        const text = screen.getAllByRole('alert').map((a) => a.textContent).join(' ')
        expect(text).toMatch(/في الماضي|in the past/i)
        expect(text).toMatch(/لم تعد متاحة|no longer available/i)
      })
    })

    it('surfaces a stale "not eligible" refusal and leaves the campaign a draft', async () => {
      vi.mocked(advertisingApi.listMyCampaigns).mockResolvedValue(page([campaign('c-1', 'X')]))
      vi.mocked(advertisingApi.submitCampaign).mockRejectedValue(new ApiError(403, 'company_not_eligible', 'no'))
      renderApp('/company/advertising')
      const row = (await screen.findAllByTestId('campaign'))[0]!
      await userEvent.click(within(row).getByRole('button', { name: SUBMIT }))
      expect(await screen.findByRole('alert')).toHaveTextContent(/موثّقة|must be verified/i)
      expect(within(row).getByRole('button', { name: SUBMIT })).toBeInTheDocument()
    })

    it('paginates the company\'s campaigns through the backend', async () => {
      vi.mocked(advertisingApi.listMyCampaigns).mockImplementation(async (p = 1) =>
        p === 1 ? page(Array.from({ length: 20 }, (_, i) => campaign(`c-${i}`, `Camp ${i}`)), 21, 'next') : page([campaign('c-20', 'Camp 20')], 21, null, 'prev'),
      )
      renderApp('/company/advertising')
      expect(await screen.findByText('Camp 0')).toBeInTheDocument()
      await userEvent.click(screen.getByRole('button', { name: /التالي|next/i }))
      expect(await screen.findByText('Camp 20')).toBeInTheDocument()
      expect(advertisingApi.listMyCampaigns).toHaveBeenCalledWith(2, expect.anything())
    })
  })
})

function adminCampaign(id: string, name: string, overrides: Partial<AdminCampaign> = {}): AdminCampaign {
  return {
    ...campaign(id, name, { status: 'PENDING_PAYMENT', quote: QUOTE }),
    company: { id: 'co-1', name: 'Dental Supply Co', account_email: 'owner@dental.example' },
    payment: { ...pendingPayment, admin_note: '', verified_by_email: null },
    ...overrides,
  }
}

const VERIFY = /تأكيد الدفع|verify payment/i
const REJECT = /رفض الدفع|reject payment/i

describe('Admin advertising review', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'ADMIN', is_staff: true }))
    vi.mocked(advertisingApi.listAdminCampaigns).mockResolvedValue(
      page([adminCampaign('c-1', 'Spring push', { provider_types: ['DOCTOR'], specialties: [dentistry], governorates: [{ ...baghdad, is_active: true }] })]),
    )
  })

  it('keeps the tab for staff only', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'MEDICAL_COMPANY' }))
    renderApp('/admin-console?tab=advertising')
    expect(await screen.findByTestId('staff-denied')).toBeInTheDocument()
    expect(advertisingApi.listAdminCampaigns).not.toHaveBeenCalled()
  })

  it('lists campaigns awaiting payment by default with everything a reviewer needs', async () => {
    renderApp('/admin-console?tab=advertising')
    const row = (await screen.findAllByTestId('admin-campaign'))[0]!
    expect(advertisingApi.listAdminCampaigns).toHaveBeenCalledWith(expect.objectContaining({ status: 'PENDING_PAYMENT', page: 1 }), expect.anything())
    expect(within(row).getByText('Dental Supply Co')).toBeInTheDocument()
    expect(within(row).getByText('owner@dental.example')).toBeInTheDocument()
    expect(within(row).getByText(/Spring push · Dental chair/)).toBeInTheDocument()
    expect(within(row).getByText(/2030-01-01 → 2030-01-10/)).toBeInTheDocument()
    expect(within(row).getByTestId('campaign-targeting')).toHaveTextContent(/طبيب|doctor/i)
    expect(within(row).getByTestId('campaign-targeting')).toHaveTextContent(/طب الأسنان|dentistry/i)
    expect(within(row).getByTestId('campaign-targeting')).toHaveTextContent(/بغداد|baghdad/i)
    expect(within(row).getByTestId('admin-quote-rate')).toHaveTextContent(/1,000|١٬٠٠٠|1000/)
    expect(within(row).getByTestId('admin-quote-days')).toHaveTextContent('10')
    expect(within(row).getByTestId('admin-quote-amount')).toHaveTextContent(/10,000|١٠٬٠٠٠|10000/)
    expect(within(row).getByTestId('admin-payment-status')).toHaveTextContent(/قيد الانتظار|pending/i)
  })

  it('has no amount input anywhere in the verification form', async () => {
    renderApp('/admin-console?tab=advertising')
    const row = (await screen.findAllByTestId('admin-campaign'))[0]!
    expect(within(row).queryByLabelText(/^المبلغ|^amount/i)).toBeNull()
    expect(within(row).getByText(/المبلغ من عرض سعر الحملة|amount is taken from the campaign/i)).toBeInTheDocument()
  })

  it('verifies with only method, reference and note, then refreshes', async () => {
    vi.mocked(advertisingApi.verifyCampaignPayment).mockResolvedValue(adminCampaign('c-1', 'Spring push', { status: 'ACTIVE' }))
    renderApp('/admin-console?tab=advertising')
    const user = userEvent.setup()
    const row = (await screen.findAllByTestId('admin-campaign'))[0]!
    await user.selectOptions(within(row).getByLabelText(/طريقة الدفع|payment method/i), 'BANK_TRANSFER')
    await user.type(within(row).getByLabelText(/المرجع الخارجي|external reference/i), 'TX-991')
    await user.type(within(row).getByLabelText(/^ملاحظة|^note/i), 'Seen in statement')
    const calls = vi.mocked(advertisingApi.listAdminCampaigns).mock.calls.length
    await user.click(within(row).getByRole('button', { name: VERIFY }))
    await waitFor(() => expect(advertisingApi.verifyCampaignPayment).toHaveBeenCalledWith('c-1', { method: 'BANK_TRANSFER', reference: 'TX-991', note: 'Seen in statement' }))
    await waitFor(() => expect(vi.mocked(advertisingApi.listAdminCampaigns).mock.calls.length).toBeGreaterThan(calls))
  })

  it('will not verify without a payment method', async () => {
    renderApp('/admin-console?tab=advertising')
    const user = userEvent.setup()
    const row = (await screen.findAllByTestId('admin-campaign'))[0]!
    await user.click(within(row).getByRole('button', { name: VERIFY }))
    expect(advertisingApi.verifyCampaignPayment).not.toHaveBeenCalled()
    expect(await within(row).findByRole('alert')).toHaveTextContent(/اختر طريقة الدفع|choose the payment method/i)
  })

  it('rejects with a reason and refreshes', async () => {
    vi.mocked(advertisingApi.rejectCampaignPayment).mockResolvedValue(adminCampaign('c-1', 'Spring push', { status: 'REJECTED' }))
    renderApp('/admin-console?tab=advertising')
    const user = userEvent.setup()
    const row = (await screen.findAllByTestId('admin-campaign'))[0]!
    await user.type(within(row).getByLabelText(/سبب الرفض|rejection reason/i), 'No transfer found')
    await user.click(within(row).getByRole('button', { name: REJECT }))
    await waitFor(() => expect(advertisingApi.rejectCampaignPayment).toHaveBeenCalledWith('c-1', 'No transfer found'))
  })

  it('ignores a second click while a verification is in flight', async () => {
    const pending = deferred<AdminCampaign>()
    vi.mocked(advertisingApi.verifyCampaignPayment).mockReturnValue(pending.promise)
    renderApp('/admin-console?tab=advertising')
    const user = userEvent.setup()
    const row = (await screen.findAllByTestId('admin-campaign'))[0]!
    await user.selectOptions(within(row).getByLabelText(/طريقة الدفع|payment method/i), 'CASH')
    await user.click(within(row).getByRole('button', { name: VERIFY }))
    const busy = await within(row).findByRole('button', { name: /جارٍ التأكيد|verifying/i })
    expect(busy).toBeDisabled()
    await user.click(busy)
    expect(advertisingApi.verifyCampaignPayment).toHaveBeenCalledTimes(1)
    pending.resolve(adminCampaign('c-1', 'Spring push', { status: 'ACTIVE' }))
  })

  it('shows the backend refusal when activation checks fail on current state', async () => {
    vi.mocked(advertisingApi.verifyCampaignPayment).mockRejectedValue(new ApiError(409, 'product_unavailable', 'no'))
    renderApp('/admin-console?tab=advertising')
    const user = userEvent.setup()
    const row = (await screen.findAllByTestId('admin-campaign'))[0]!
    await user.selectOptions(within(row).getByLabelText(/طريقة الدفع|payment method/i), 'CASH')
    await user.click(within(row).getByRole('button', { name: VERIFY }))
    expect(await within(row).findByRole('alert')).toHaveTextContent(/غير متاح حاليًا للإعلان|not currently available for advertising/i)
  })

  it('offers no decision on a campaign that is not awaiting payment and filters through the backend', async () => {
    vi.mocked(advertisingApi.listAdminCampaigns).mockResolvedValue(
      page([adminCampaign('a-1', 'Live', { status: 'ACTIVE', payment: { ...pendingPayment, status: 'VERIFIED', method: 'CASH', reference: 'R-1', verified_at: '2026-10-02T00:00:00Z', admin_note: 'ok', verified_by_email: 'admin@example.com' } })]),
    )
    renderApp('/admin-console?tab=advertising&filter=ACTIVE')
    const row = (await screen.findAllByTestId('admin-campaign'))[0]!
    expect(advertisingApi.listAdminCampaigns).toHaveBeenCalledWith(expect.objectContaining({ status: 'ACTIVE' }), expect.anything())
    expect(within(row).queryByRole('button', { name: VERIFY })).toBeNull()
    expect(within(row).queryByRole('button', { name: REJECT })).toBeNull()
    expect(within(row).getByText(/R-1/)).toBeInTheDocument()
    expect(within(row).getByText(/admin@example.com/)).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText(/حالة الحملة|campaign status/i), 'REJECTED')
    await waitFor(() => expect(advertisingApi.listAdminCampaigns).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'REJECTED' }), expect.anything()))
  })

  it('shows the empty state', async () => {
    vi.mocked(advertisingApi.listAdminCampaigns).mockResolvedValue(page([]))
    renderApp('/admin-console?tab=advertising')
    expect(await screen.findByTestId('admin-empty-campaigns')).toBeInTheDocument()
  })
})

function product(id: string, title: string): MarketplaceProduct {
  return {
    id,
    title,
    description: '',
    brand: 'Acme',
    model_name: 'X1',
    price: '1500000.00',
    currency: 'IQD',
    category: dental,
    company: { id: 'co-1', name: 'Dental Supply Co', governorate: baghdad, city: null, website: '', public_email: '', phone: '' },
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
  }
}

const ad = (id: string, p: MarketplaceProduct): SponsoredCampaign => ({ id, sponsored: true, starts_on: '2030-01-01', ends_on: '2030-01-10', product: p })

describe('Sponsored marketplace section', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PROVIDER' }))
    vi.mocked(marketplaceApi.listCategories).mockResolvedValue([dental])
    vi.mocked(marketplaceApi.listTargetedProducts).mockResolvedValue(page([product('o-1', 'Organic scaler')]))
  })

  it('shows the backend\'s ads with a visible Sponsored label, linking the existing product page', async () => {
    vi.mocked(advertisingApi.listSponsored).mockResolvedValue(page([ad('ad-1', product('p-7', 'Promoted chair')), ad('ad-2', product('p-8', 'Promoted lamp'))]))
    renderApp('/marketplace')
    const cards = await screen.findAllByTestId('sponsored-ad')
    expect(cards).toHaveLength(2) // exactly what the backend returned
    for (const card of cards) expect(within(card).getByText(/إعلان ممول|^sponsored$/i)).toBeInTheDocument()
    expect(within(cards[0]!).getByRole('link', { name: 'Promoted chair' })).toHaveAttribute('href', '/marketplace/products/p-7')
    expect(screen.getByRole('heading', { name: /إعلانات ممولة|^sponsored$/i })).toBeInTheDocument()
    expect(advertisingApi.listSponsored).toHaveBeenCalledWith(1, expect.anything()) // no client-side targeting or filtering input
    // the organic catalogue is separate and unlabelled
    const organic = await screen.findAllByTestId('marketplace-product')
    expect(organic).toHaveLength(1)
    expect(within(organic[0]!).queryByText(/إعلان ممول|sponsored/i)).toBeNull()
  })

  it('shows loading inside the sponsored section while organic products load independently', async () => {
    const pending = deferred<ReturnType<typeof page<SponsoredCampaign>>>()
    vi.mocked(advertisingApi.listSponsored).mockReturnValue(pending.promise)
    renderApp('/marketplace')
    expect(await screen.findByTestId('sponsored-loading')).toBeInTheDocument()
    expect((await screen.findAllByTestId('marketplace-product')).length).toBe(1)
    pending.resolve(page([]))
    await waitFor(() => expect(screen.queryByTestId('sponsored-loading')).toBeNull())
  })

  it('keeps the organic marketplace working when the ads endpoint fails, and lets the provider retry', async () => {
    vi.mocked(advertisingApi.listSponsored).mockRejectedValueOnce(new ApiError(500, 'server_error', 'Boom.')).mockResolvedValue(page([ad('ad-1', product('p-7', 'Promoted chair'))]))
    renderApp('/marketplace')
    const failure = await screen.findByTestId('sponsored-error')
    expect(failure).toHaveTextContent(/تعذّر تحميل المنتجات الممولة|could not be loaded/i)
    expect(await screen.findByText('Organic scaler')).toBeInTheDocument() // the catalogue is untouched
    await userEvent.click(within(failure).getByRole('button', { name: /إعادة المحاولة|try again|retry/i }))
    expect(await screen.findByText('Promoted chair')).toBeInTheDocument()
  })

  it('renders no sponsored section when there are no ads, and invents none', async () => {
    vi.mocked(advertisingApi.listSponsored).mockResolvedValue(page([]))
    renderApp('/marketplace')
    expect(await screen.findByText('Organic scaler')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByTestId('sponsored-loading')).toBeNull())
    expect(screen.queryByTestId('sponsored-results')).toBeNull()
    expect(screen.queryAllByTestId('sponsored-ad')).toHaveLength(0)
  })

  it('does not load ads for accounts that cannot use the marketplace', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PATIENT' }))
    renderApp('/marketplace')
    expect(await screen.findByTestId('role-denied')).toBeInTheDocument()
    expect(advertisingApi.listSponsored).not.toHaveBeenCalled()
  })
})

describe('Advertising translations', () => {
  const groups: Record<string, string[]> = {
    campaignStatus: ['DRAFT', 'PENDING_PAYMENT', 'ACTIVE', 'REJECTED', 'CANCELLED'],
    paymentStatus: ['PENDING', 'VERIFIED', 'REJECTED'],
    paymentMethods: ['BANK_TRANSFER', 'CASH', 'EXCHANGE_OFFICE', 'OTHER'],
  }
  const keys = [
    ...Object.entries(groups).flatMap(([g, codes]) => codes.map((c) => `${g}.${c}`)),
    'advertising.title', 'advertising.sponsored', 'advertising.sponsoredSection', 'advertising.pendingTitle', 'advertising.pendingBody',
    'advertising.pricingUnavailable', 'advertising.quote.title', 'advertising.quote.note', 'advertising.rejectedBody', 'advertising.cancelledBody',
    'admin.advertising.verify', 'admin.advertising.reject', 'admin.advertising.amountNote', 'nav.advertising', 'admin.tabs.advertising',
    'apiErrors.pricing_unavailable', 'apiErrors.campaign_not_editable', 'apiErrors.campaign_not_submittable', 'apiErrors.company_not_eligible',
    'apiErrors.product_unavailable', 'apiErrors.payment_not_pending', 'apiErrors.campaign_ended', 'apiErrors.end_in_past',
  ]

  it.each(['ar', 'en'])('has every advertising string in %s (no raw keys or enum codes)', (lng) => {
    const t = i18n.getFixedT(lng)
    for (const key of keys) {
      const text = t(key)
      expect(text, key).not.toBe(key)
      expect(text, key).not.toMatch(/^[A-Z_]+$/)
    }
    expect(t('advertising.sponsored')).toBe(lng === 'ar' ? 'إعلان ممول' : 'Sponsored')
    expect(t('advertising.sponsoredSection')).toBe(lng === 'ar' ? 'إعلانات ممولة' : 'Sponsored')
  })
})
