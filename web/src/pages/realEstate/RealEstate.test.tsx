import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as realEstateApi from '../../api/endpoints/realEstate'
import * as referenceApi from '../../api/endpoints/reference'
import * as providersApi from '../../api/endpoints/providers'
import { tokenStore } from '../../api/tokens'
import type { City, OwnerDashboard, OwnerListing, PropertyListing, RealEstateSeller } from '../../api'
import { baghdad, basra } from '../../test/providerFixtures'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

// These pages chain several backend loads; be generous so a slow or busy machine does not flake (per test file).
configure({ asyncUtilTimeout: 5000 })

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/realEstate')
vi.mock('../../api/endpoints/reference')
vi.mock('../../api/endpoints/providers')

const karrada: City = { id: 'c-karrada', governorate: 'g-baghdad', slug: 'karrada', name_ar: 'الكرادة', name_en: 'Karrada' }
const mansour: City = { id: 'c-mansour', governorate: 'g-baghdad', slug: 'mansour', name_ar: 'المنصور', name_en: 'Mansour' }
const ashar: City = { id: 'c-ashar', governorate: 'g-basra', slug: 'ashar', name_ar: 'العشار', name_en: 'Ashar' }

const page = <T,>(results: T[], count = results.length, next: string | null = null, previous: string | null = null) => ({ count, next, previous, results })

function listing(id: string, title: string, overrides: Partial<PropertyListing> = {}): PropertyListing {
  return {
    id,
    title,
    description: 'Bright ground floor.',
    property_type: 'CLINIC',
    transaction_type: 'RENT',
    governorate: baghdad,
    city: karrada,
    district: 'Karrada',
    latitude: null,
    longitude: null,
    area_sqm: '120.00',
    price: '1500000.00',
    currency: 'IQD',
    suitable_uses: ['CLINIC', 'LABORATORY'],
    facilities: 'Parking, lift',
    contact_method: 'PHONE',
    contact_phone: '07700000000',
    contact_email: null,
    seller: { id: 's-1', display_name: 'Al-Noor Realty', seller_type: 'AGENT' },
    published_at: '2026-09-30T00:00:00Z',
    expires_at: '2099-01-01T00:00:00Z',
    created_at: '2026-09-30T00:00:00Z',
    updated_at: '2026-09-30T00:00:00Z',
    ...overrides,
  }
}

function ownerListing(id: string, title: string, overrides: Partial<OwnerListing> = {}): OwnerListing {
  return {
    id,
    title,
    description: 'Bright ground floor.',
    property_type: 'CLINIC',
    transaction_type: 'RENT',
    governorate: baghdad,
    city: null,
    district: 'Karrada',
    latitude: null,
    longitude: null,
    area_sqm: '120.00',
    price: '1500000.00',
    currency: 'IQD',
    suitable_uses: ['CLINIC'],
    facilities: '',
    contact_method: 'PHONE',
    contact_phone: '07700000000',
    contact_email: '',
    publication_status: 'DRAFT',
    published_at: null,
    expires_at: '2099-01-01T00:00:00Z',
    is_public: false,
    is_expired: false,
    created_at: '2026-09-30T00:00:00Z',
    updated_at: '2026-09-30T00:00:00Z',
    ...overrides,
  }
}

const seller: RealEstateSeller = {
  id: 's-1',
  seller_type: 'AGENT',
  display_name: 'Al-Noor Realty',
  about: '',
  phone: '',
  public_email: '',
  created_at: '2026-09-30T00:00:00Z',
  updated_at: '2026-09-30T00:00:00Z',
}

const dashboard: OwnerDashboard = {
  listings_total: 7,
  listings_draft: 3,
  listings_published: 4,
  listings_visible: 2,
  listings_expired: 1,
  listings_sale: 5,
  listings_rent: 2,
}

const PUBLISH = /^نشر$|^publish$/i
const UNPUBLISH = /إلغاء النشر|unpublish/i
const EDIT = /تعديل|edit/i

describe('Public real-estate catalogue', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad, basra])
    vi.mocked(referenceApi.listCities).mockImplementation(async (g) => (g === 'g-baghdad' ? [karrada, mansour] : [ashar]))
  })

  it('shows loading, then exactly the listings the backend returned', async () => {
    const pending = deferred<ReturnType<typeof page<PropertyListing>>>()
    vi.mocked(realEstateApi.listListings).mockReturnValue(pending.promise)
    renderApp('/real-estate')
    expect((await screen.findAllByText(/جارٍ تحميل العقارات|loading properties/i)).length).toBeGreaterThan(0)
    pending.resolve(page([listing('l-1', 'Karrada clinic', { price: null }), listing('l-2', 'Lab floor', { transaction_type: 'SALE', suitable_uses: ['LABORATORY'] })]))
    const cards = await screen.findAllByTestId('realestate-listing')
    expect(cards).toHaveLength(2) // nothing added, removed or reordered on the client
    expect(within(cards[0]!).getByRole('link', { name: 'Karrada clinic' })).toHaveAttribute('href', '/real-estate/l-1')
    expect(within(cards[0]!).getByText(/السعر عند الطلب|price on request/i)).toBeInTheDocument()
    expect(within(cards[0]!).getByText(/للإيجار|for rent/i)).toBeInTheDocument()
    expect(within(cards[0]!).getByText(/عيادة|clinic/i, { selector: '[data-testid="realestate-uses"] *' })).toBeInTheDocument()
    expect(within(cards[1]!).getByText(/للبيع|for sale/i)).toBeInTheDocument()
    expect(screen.getByTestId('realestate-count')).toHaveTextContent('2')
  })

  it('sends every filter to the backend and keeps them in the URL', async () => {
    vi.mocked(realEstateApi.listListings).mockResolvedValue(page([]))
    const { router } = renderApp('/real-estate?transaction_type=SALE&min_price=1000&suitable_use=PHARMACY&page=1')
    await waitFor(() =>
      expect(realEstateApi.listListings).toHaveBeenCalledWith(expect.objectContaining({ transaction_type: 'SALE', min_price: '1000', suitable_use: 'PHARMACY' }), expect.anything()),
    )
    const user = userEvent.setup()
    await user.selectOptions(await screen.findByLabelText(/نوع العقار|property type/i), 'MEDICAL_CENTER')
    await waitFor(() => expect(router.state.location.search).toContain('property_type=MEDICAL_CENTER'))
    expect(router.state.location.search).toContain('transaction_type=SALE')
    await waitFor(() =>
      expect(realEstateApi.listListings).toHaveBeenLastCalledWith(expect.objectContaining({ property_type: 'MEDICAL_CENTER', transaction_type: 'SALE' }), expect.anything()),
    )

    await user.selectOptions(screen.getByLabelText(/المحافظة|governorate/i), 'g-baghdad')
    await waitFor(() => expect(referenceApi.listCities).toHaveBeenCalledWith('g-baghdad', expect.anything()))
    await user.selectOptions(await screen.findByLabelText(/المدينة|city/i), 'c-karrada')
    await user.selectOptions(screen.getByLabelText(/الترتيب|sort by/i), 'price')
    await waitFor(() =>
      expect(realEstateApi.listListings).toHaveBeenLastCalledWith(expect.objectContaining({ governorate: 'g-baghdad', city: 'c-karrada', ordering: 'price' }), expect.anything()),
    )
  })

  it('applies free-text and numeric filters on submit, not per keystroke', async () => {
    vi.mocked(realEstateApi.listListings).mockResolvedValue(page([]))
    renderApp('/real-estate')
    const user = userEvent.setup()
    await screen.findByTestId('realestate-empty')
    const calls = vi.mocked(realEstateApi.listListings).mock.calls.length
    await user.type(screen.getByLabelText(/^بحث$|^search$/i), 'karrada')
    await user.type(screen.getByLabelText(/أقل سعر|minimum price/i), '500000')
    await user.type(screen.getByLabelText(/أعلى مساحة|maximum area/i), '300')
    expect(vi.mocked(realEstateApi.listListings).mock.calls.length).toBe(calls) // nothing sent while typing
    await user.click(screen.getByRole('button', { name: /^بحث$|^search$/i }))
    await waitFor(() =>
      expect(realEstateApi.listListings).toHaveBeenLastCalledWith(expect.objectContaining({ search: 'karrada', min_price: '500000', max_area: '300' }), expect.anything()),
    )
  })

  it('clears every filter', async () => {
    vi.mocked(realEstateApi.listListings).mockResolvedValue(page([]))
    const { router } = renderApp('/real-estate?transaction_type=RENT&search=x&min_area=10')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /^مسح$|^clear$/i, hidden: false }).catch(() => screen.getAllByRole('button', { name: /مسح|clear/i })[0]!))
    await waitFor(() => expect(router.state.location.search).toBe(''))
  })

  it('paginates through the backend', async () => {
    vi.mocked(realEstateApi.listListings).mockImplementation(async (filters) =>
      (filters?.page ?? 1) === 1
        ? page(Array.from({ length: 20 }, (_, i) => listing(`l-${i}`, `Item ${i}`)), 21, 'next')
        : page([listing('l-20', 'Item 20')], 21, null, 'prev'),
    )
    renderApp('/real-estate')
    expect(await screen.findByText('Item 0')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /التالي|next/i }))
    expect(await screen.findByText('Item 20')).toBeInTheDocument()
    expect(realEstateApi.listListings).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }), expect.anything())
  })

  it('shows the empty state and an error with retry', async () => {
    vi.mocked(realEstateApi.listListings).mockResolvedValueOnce(page([]))
    renderApp('/real-estate')
    expect(await screen.findByTestId('realestate-empty')).toBeInTheDocument()

    vi.mocked(realEstateApi.listListings).mockRejectedValueOnce(new ApiError(500, 'server_error', 'Boom.')).mockResolvedValue(page([listing('l-1', 'Recovered')]))
    renderApp('/real-estate')
    const retry = await screen.findByRole('button', { name: /إعادة المحاولة|try again|retry/i })
    await userEvent.click(retry)
    expect(await screen.findByText('Recovered')).toBeInTheDocument()
  })

  it('needs no account, and never fabricates listings', async () => {
    vi.mocked(realEstateApi.listListings).mockResolvedValue(page([]))
    renderApp('/real-estate')
    expect(await screen.findByTestId('realestate-empty')).toBeInTheDocument()
    expect(screen.queryAllByTestId('realestate-listing')).toHaveLength(0)
    expect(authApi.getMe).not.toHaveBeenCalled()
  })
})

describe('Public listing detail', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
  })

  it('shows the listing with only the contact values the backend returned', async () => {
    vi.mocked(realEstateApi.getListing).mockResolvedValue(
      listing('l-1', 'Karrada clinic', { latitude: '33.315200', longitude: '44.366100', contact_method: 'EMAIL', contact_phone: null, contact_email: 'agent@example.com' }),
    )
    renderApp('/real-estate/l-1')
    expect(await screen.findByRole('heading', { name: 'Karrada clinic' })).toBeInTheDocument()
    expect(screen.getByTestId('listing-price')).toHaveTextContent(/1,500,000|١٬٥٠٠٬٠٠٠|1500000/)
    expect(screen.getByTestId('listing-coordinates')).toHaveTextContent('33.315200, 44.366100')
    expect(screen.getByTestId('listing-email')).toHaveTextContent('agent@example.com')
    expect(screen.queryByTestId('listing-phone')).toBeNull()
    expect(screen.getByTestId('listing-uses')).toHaveTextContent(/عيادة|clinic/i)
    expect(screen.getByText('Al-Noor Realty')).toBeInTheDocument()
    expect(screen.getByText('Parking, lift')).toBeInTheDocument()
  })

  it('hides coordinates when there are none and shows price on request', async () => {
    vi.mocked(realEstateApi.getListing).mockResolvedValue(listing('l-2', 'Land', { price: null }))
    renderApp('/real-estate/l-2')
    expect(await screen.findByRole('heading', { name: 'Land' })).toBeInTheDocument()
    expect(screen.queryByTestId('listing-coordinates')).toBeNull()
    expect(screen.getByTestId('listing-price')).toHaveTextContent(/السعر عند الطلب|price on request/i)
  })

  it('answers a hidden or unknown listing with one non-disclosing message', async () => {
    vi.mocked(realEstateApi.getListing).mockRejectedValue(new ApiError(404, 'not_found', 'Not found.'))
    renderApp('/real-estate/hidden')
    expect(await screen.findByText(/هذا العقار غير متاح|this property is not available/i)).toBeInTheDocument()
  })
})

describe('Home page real-estate card', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad])
    vi.mocked(providersApi.listProviders).mockResolvedValue(page([]))
  })

  it('is live for visitors: it links to the catalogue and is not marked "soon"', async () => {
    renderApp('/')
    const card = (await screen.findByText(/عيادات وعقارات مخصّصة|clinics and properties suited/i)).closest('article, div, li') as HTMLElement
    const link = within(card.parentElement ?? card).getAllByRole('link', { name: /تصفّح|browse/i }).find((a) => a.getAttribute('href') === '/real-estate')
    expect(link).toBeDefined()
    const modules = screen.getAllByText(/العقارات الطبية|medical real estate/i)
    for (const node of modules) expect(node.closest('[data-testid="feature-upcoming"], li')?.textContent ?? '').not.toMatch(/قريبًا|قريباً|soon/i)
  })

  it('sends a real-estate seller to their workspace', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'REAL_ESTATE_SELLER' }))
    renderApp('/')
    await waitFor(() => expect(screen.getAllByRole('link').some((a) => a.getAttribute('href') === '/real-estate/owner')).toBe(true))
  })
})

describe('Header navigation', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad])
    vi.mocked(realEstateApi.listListings).mockResolvedValue(page([]))
  })
  const hrefs = () => screen.getAllByRole('link').map((a) => a.getAttribute('href'))

  it('lets anyone browse real estate, without offering the workspace', async () => {
    renderApp('/real-estate')
    await screen.findByTestId('realestate-empty')
    expect(hrefs()).toContain('/real-estate')
    expect(hrefs()).not.toContain('/real-estate/owner')
  })

  it('gives a real-estate seller an obvious way to their workspace', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'REAL_ESTATE_SELLER' }))
    renderApp('/real-estate')
    await waitFor(() => expect(hrefs()).toContain('/real-estate/owner'))
  })

  it.each(['PATIENT', 'PROVIDER', 'MEDICAL_COMPANY'] as const)('does not show the workspace link to %s accounts', async (role) => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role }))
    renderApp('/real-estate')
    await screen.findByTestId('realestate-empty')
    await waitFor(() => expect(screen.getAllByRole('link').some((a) => a.getAttribute('href') === '/profile')).toBe(true))
    expect(hrefs()).not.toContain('/real-estate/owner')
  })
})

describe('Seller workspace access', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
  })

  it.each(['PATIENT', 'PROVIDER', 'MEDICAL_COMPANY'] as const)('keeps the workspace away from %s accounts', async (role) => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role }))
    renderApp('/real-estate/owner')
    expect(await screen.findByTestId('role-denied')).toBeInTheDocument()
    expect(realEstateApi.getMySeller).not.toHaveBeenCalled()
  })

  it('sends an anonymous visitor to log in', async () => {
    tokenStore.clear()
    const { router } = renderApp('/real-estate/owner')
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
  })

  it('does not treat "owner" as a listing id', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'REAL_ESTATE_SELLER' }))
    vi.mocked(realEstateApi.getMySeller).mockRejectedValue(new ApiError(404, 'not_found', 'none'))
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad])
    renderApp('/real-estate/owner')
    expect(await screen.findByTestId('seller-onboarding')).toBeInTheDocument()
    expect(realEstateApi.getListing).not.toHaveBeenCalled()
  })
})

describe('Seller workspace', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'REAL_ESTATE_SELLER' }))
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad, basra])
    vi.mocked(referenceApi.listCities).mockImplementation(async (g) => (g === 'g-baghdad' ? [karrada, mansour] : [ashar]))
    vi.mocked(realEstateApi.getMySeller).mockResolvedValue(seller)
    vi.mocked(realEstateApi.getOwnerDashboard).mockResolvedValue(dashboard)
    vi.mocked(realEstateApi.listMyListings).mockResolvedValue(page([]))
  })

  it('onboards a seller who has no profile yet', async () => {
    vi.mocked(realEstateApi.getMySeller).mockRejectedValue(new ApiError(404, 'not_found', 'none'))
    vi.mocked(realEstateApi.createMySeller).mockResolvedValue(seller)
    renderApp('/real-estate/owner')
    const user = userEvent.setup()
    const form = await screen.findByTestId('seller-onboarding')
    await user.click(within(form).getByRole('button', { name: /إنشاء الملف|create profile/i }))
    expect(realEstateApi.createMySeller).not.toHaveBeenCalled() // type and name required client-side
    await user.selectOptions(within(form).getByLabelText(/نوع الحساب|account type/i), 'AGENT')
    await user.type(within(form).getByLabelText(/الاسم المعروض|display name/i), 'Al-Noor Realty')
    await user.click(within(form).getByRole('button', { name: /إنشاء الملف|create profile/i }))
    await waitFor(() => expect(realEstateApi.createMySeller).toHaveBeenCalledWith(expect.objectContaining({ seller_type: 'AGENT', display_name: 'Al-Noor Realty' })))
    // the payload never carries ownership or account identity
    expect(Object.keys(vi.mocked(realEstateApi.createMySeller).mock.calls[0]![0])).not.toEqual(expect.arrayContaining(['account', 'role', 'is_staff']))
  })

  it('shows the backend dashboard counts and never counts client-side', async () => {
    vi.mocked(realEstateApi.listMyListings).mockResolvedValue(page([ownerListing('d-1', 'Only one row')]))
    renderApp('/real-estate/owner')
    expect(await screen.findByTestId('owner-dashboard')).toBeInTheDocument()
    expect(screen.getByTestId('stat-total')).toHaveTextContent('7') // one listing on the page, backend says 7
    expect(screen.getByTestId('stat-draft')).toHaveTextContent('3')
    expect(screen.getByTestId('stat-published')).toHaveTextContent('4')
    expect(screen.getByTestId('stat-visible')).toHaveTextContent('2')
    expect(screen.getByTestId('stat-expired')).toHaveTextContent('1')
    expect(screen.getByTestId('stat-sale')).toHaveTextContent('5')
    expect(screen.getByTestId('stat-rent')).toHaveTextContent('2')
  })

  it('creates a draft with only owner-editable data and structured uses', async () => {
    vi.mocked(realEstateApi.createMyListing).mockResolvedValue(ownerListing('n-1', 'New clinic'))
    renderApp('/real-estate/owner')
    const user = userEvent.setup()
    const form = await screen.findByTestId('listing-form')
    await user.click(within(form).getByRole('button', { name: /إنشاء الإعلان|create listing/i }))
    expect(realEstateApi.createMyListing).not.toHaveBeenCalled() // title, types and governorate are required
    await user.type(within(form).getByLabelText(/عنوان الإعلان|listing title/i), 'New clinic')
    await user.selectOptions(within(form).getByLabelText(/نوع العقار|property type/i), 'CLINIC')
    await user.selectOptions(within(form).getByLabelText(/نوع الصفقة|transaction/i), 'RENT')
    await user.selectOptions(within(form).getByLabelText(/^المحافظة|^governorate/i), 'g-baghdad')
    await user.click(within(form).getByRole('checkbox', { name: /عيادة|clinic/i }))
    await user.click(within(form).getByRole('checkbox', { name: /مختبر|laboratory/i }))
    await user.type(within(form).getByLabelText(/المساحة|area/i), '95.5')
    await user.click(within(form).getByRole('button', { name: /إنشاء الإعلان|create listing/i }))
    await waitFor(() => expect(realEstateApi.createMyListing).toHaveBeenCalled())
    const payload = vi.mocked(realEstateApi.createMyListing).mock.calls[0]![0]
    expect(payload).toMatchObject({ title: 'New clinic', property_type: 'CLINIC', transaction_type: 'RENT', governorate: 'g-baghdad', area_sqm: '95.5', price: null, suitable_uses: ['CLINIC', 'LABORATORY'] })
    // lifecycle, ownership and derived state are server-controlled
    for (const forbidden of ['seller', 'seller_id', 'account', 'publication_status', 'published_at', 'is_public', 'is_expired', 'images']) {
      expect(payload).not.toHaveProperty(forbidden)
    }
  })

  it('refuses one coordinate without the other, client-side, but leaves the rest to the backend', async () => {
    renderApp('/real-estate/owner')
    const user = userEvent.setup()
    const form = await screen.findByTestId('listing-form')
    await user.type(within(form).getByLabelText(/عنوان الإعلان|listing title/i), 'T')
    await user.selectOptions(within(form).getByLabelText(/نوع العقار|property type/i), 'CLINIC')
    await user.selectOptions(within(form).getByLabelText(/نوع الصفقة|transaction/i), 'SALE')
    await user.selectOptions(within(form).getByLabelText(/^المحافظة|^governorate/i), 'g-baghdad')
    await user.type(within(form).getByLabelText(/خط العرض|latitude/i), '33.3')
    await user.click(within(form).getByRole('button', { name: /إنشاء الإعلان|create listing/i }))
    expect(realEstateApi.createMyListing).not.toHaveBeenCalled()
    expect(within(form).getByText(/أدخل خط العرض وخط الطول معًا|latitude and longitude together/i)).toBeInTheDocument()
  })

  it('shows backend validation errors on the form fields', async () => {
    vi.mocked(realEstateApi.createMyListing).mockRejectedValue(
      new ApiError(400, 'validation_error', 'Validation failed.', { area_sqm: ['too small'] }, { area_sqm: ['area_invalid'] }),
    )
    renderApp('/real-estate/owner')
    const user = userEvent.setup()
    const form = await screen.findByTestId('listing-form')
    await user.type(within(form).getByLabelText(/عنوان الإعلان|listing title/i), 'T')
    await user.selectOptions(within(form).getByLabelText(/نوع العقار|property type/i), 'CLINIC')
    await user.selectOptions(within(form).getByLabelText(/نوع الصفقة|transaction/i), 'SALE')
    await user.selectOptions(within(form).getByLabelText(/^المحافظة|^governorate/i), 'g-baghdad')
    await user.click(within(form).getByRole('button', { name: /إنشاء الإعلان|create listing/i }))
    expect(await within(form).findByText(/يجب أن تكون المساحة أكبر من صفر|area must be greater than zero/i)).toBeInTheDocument()
  })

  describe('publication', () => {
    it('offers Publish only where the loaded data says it can succeed, and says what is missing otherwise', async () => {
      vi.mocked(realEstateApi.listMyListings).mockResolvedValue(
        page([
          ownerListing('ready', 'Ready'),
          ownerListing('no-uses', 'No uses', { suitable_uses: [] }),
          ownerListing('no-area', 'No area', { area_sqm: null }),
          ownerListing('no-expiry', 'No expiry', { expires_at: null }),
          ownerListing('past', 'Past expiry', { expires_at: '2001-01-01T00:00:00Z' }),
          ownerListing('no-phone', 'No phone', { contact_phone: '' }),
          ownerListing('live', 'Live', { publication_status: 'PUBLISHED', is_public: true }),
        ]),
      )
      renderApp('/real-estate/owner')
      const rows = await screen.findAllByTestId('owner-listing')
      const publishButton = (i: number) => within(rows[i]!).queryByRole('button', { name: PUBLISH })
      expect(publishButton(0)).toBeInTheDocument()
      for (const i of [1, 2, 3, 4, 5]) {
        expect(publishButton(i)).toBeNull()
        expect(within(rows[i]!).getByTestId('owner-listing-gaps')).toBeInTheDocument()
      }
      expect(within(rows[1]!).getByTestId('owner-listing-gaps')).toHaveTextContent(/استخدام طبي مناسب|suitable medical use/i)
      expect(within(rows[2]!).getByTestId('owner-listing-gaps')).toHaveTextContent(/المساحة|area/i)
      expect(within(rows[3]!).getByTestId('owner-listing-gaps')).toHaveTextContent(/تاريخ انتهاء|expiration/i)
      expect(within(rows[5]!).getByTestId('owner-listing-gaps')).toHaveTextContent(/بيانات التواصل|contact details/i)
      // a published listing offers Unpublish, never Publish
      expect(within(rows[6]!).getByRole('button', { name: UNPUBLISH })).toBeInTheDocument()
      expect(publishButton(6)).toBeNull()
    })

    it('publishes and unpublishes through the backend, refreshing the dashboard', async () => {
      vi.mocked(realEstateApi.listMyListings).mockResolvedValue(page([ownerListing('d-1', 'Draft'), ownerListing('a-1', 'Live', { publication_status: 'PUBLISHED', is_public: true })]))
      vi.mocked(realEstateApi.setMyListingPublished).mockImplementation(async (id, published) => ownerListing(id, 'x', { publication_status: published ? 'PUBLISHED' : 'DRAFT' }))
      renderApp('/real-estate/owner')
      const user = userEvent.setup()
      const rows = await screen.findAllByTestId('owner-listing')
      const dashboardCalls = vi.mocked(realEstateApi.getOwnerDashboard).mock.calls.length
      await user.click(within(rows[0]!).getByRole('button', { name: PUBLISH }))
      await waitFor(() => expect(realEstateApi.setMyListingPublished).toHaveBeenCalledWith('d-1', true))
      await user.click(within(rows[1]!).getByRole('button', { name: UNPUBLISH }))
      await waitFor(() => expect(realEstateApi.setMyListingPublished).toHaveBeenCalledWith('a-1', false))
      await waitFor(() => expect(vi.mocked(realEstateApi.getOwnerDashboard).mock.calls.length).toBeGreaterThan(dashboardCalls))
    })

    it('shows the button busy and ignores a second click while publishing', async () => {
      vi.mocked(realEstateApi.listMyListings).mockResolvedValue(page([ownerListing('d-1', 'Draft')]))
      const pending = deferred<OwnerListing>()
      vi.mocked(realEstateApi.setMyListingPublished).mockReturnValue(pending.promise)
      renderApp('/real-estate/owner')
      const user = userEvent.setup()
      const row = (await screen.findAllByTestId('owner-listing'))[0]!
      const button = within(row).getByRole('button', { name: PUBLISH })
      await user.click(button)
      await waitFor(() => expect(within(row).getByRole('button', { name: /جارٍ النشر|publishing/i })).toBeDisabled())
      await user.click(within(row).getByRole('button', { name: /جارٍ النشر|publishing/i }))
      expect(realEstateApi.setMyListingPublished).toHaveBeenCalledTimes(1)
      pending.resolve(ownerListing('d-1', 'Draft', { publication_status: 'PUBLISHED' }))
    })

    it('shows every typed reason when the backend gate refuses (state changed after load)', async () => {
      vi.mocked(realEstateApi.listMyListings).mockResolvedValue(page([ownerListing('d-1', 'Draft')]))
      vi.mocked(realEstateApi.setMyListingPublished).mockRejectedValue(
        new ApiError(400, 'validation_error', 'Validation failed.', { expires_at: ['x'], governorate: ['y'] }, { expires_at: ['expiry_in_past'], governorate: ['geography_inactive'] }),
      )
      renderApp('/real-estate/owner')
      const row = (await screen.findAllByTestId('owner-listing'))[0]!
      await userEvent.click(within(row).getByRole('button', { name: PUBLISH }))
      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent(/يجب أن يكون تاريخ الانتهاء في المستقبل|expiration date must be in the future/i)
      expect(alert).toHaveTextContent(/لم تعد متاحة|no longer available/i)
      expect(within(row).getByRole('button', { name: PUBLISH })).toBeInTheDocument() // still a draft; the owner can fix and retry
    })

    it('surfaces a non-field refusal such as an ineligible seller account', async () => {
      vi.mocked(realEstateApi.listMyListings).mockResolvedValue(page([ownerListing('d-1', 'Draft')]))
      vi.mocked(realEstateApi.setMyListingPublished).mockRejectedValue(new ApiError(403, 'seller_not_eligible', 'Not eligible.'))
      renderApp('/real-estate/owner')
      const row = (await screen.findAllByTestId('owner-listing'))[0]!
      await userEvent.click(within(row).getByRole('button', { name: PUBLISH }))
      expect(await screen.findByRole('alert')).toHaveTextContent(/حساب بائع عقارات فعّالًا|active real-estate seller account/i)
    })

    it('marks an expired listing and explains how to bring it back', async () => {
      vi.mocked(realEstateApi.listMyListings).mockResolvedValue(
        page([ownerListing('e-1', 'Expired', { publication_status: 'PUBLISHED', is_expired: true, is_public: false, expires_at: '2001-01-01T00:00:00Z' })]),
      )
      renderApp('/real-estate/owner')
      const row = (await screen.findAllByTestId('owner-listing'))[0]!
      expect(within(row).getAllByText(/منتهٍ|expired/i).length).toBeGreaterThan(0)
      expect(within(row).getByText(/مدّد تاريخ الانتهاء|extend the expiration date/i)).toBeInTheDocument()
      expect(within(row).getByRole('button', { name: UNPUBLISH })).toBeInTheDocument()
    })
  })

  it('paginates the seller\'s own listings through the backend', async () => {
    vi.mocked(realEstateApi.listMyListings).mockImplementation(async (p = 1) =>
      p === 1 ? page(Array.from({ length: 20 }, (_, i) => ownerListing(`o-${i}`, `Own ${i}`)), 21, 'next') : page([ownerListing('o-20', 'Own 20')], 21, null, 'prev'),
    )
    renderApp('/real-estate/owner')
    expect(await screen.findByText('Own 0')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /التالي|next/i }))
    expect(await screen.findByText('Own 20')).toBeInTheDocument()
    expect(realEstateApi.listMyListings).toHaveBeenCalledWith(2, expect.anything())
  })

  describe('reference data that is no longer active', () => {
    const openEditor = async (listingRow: OwnerListing) => {
      vi.mocked(realEstateApi.listMyListings).mockResolvedValue(page([listingRow]))
      renderApp('/real-estate/owner')
      const user = userEvent.setup()
      const row = (await screen.findAllByTestId('owner-listing'))[0]!
      await user.click(within(row).getByRole('button', { name: EDIT }))
      const form = await screen.findByTestId('listing-form')
      return { user, form }
    }
    const retired = { id: 'g-retired', country: 'c-iq', slug: 'retired', name_ar: 'محافظة قديمة', name_en: 'Old governorate' }

    it('keeps a deactivated governorate as the selected current value, labelled, and never as a destination', async () => {
      const { user, form } = await openEditor(ownerListing('d-1', 'Draft', { governorate: retired }))
      const select = within(form).getByLabelText(/^المحافظة|^governorate/i)
      expect(select).toHaveValue('g-retired') // the actual state, not the placeholder
      const current = within(select).getByRole('option', { name: /محافظة قديمة|Old governorate/ })
      expect(current).toHaveTextContent(/لم تعد متاحة|no longer available/)
      expect(current).toBeEnabled()
      expect(within(select).getAllByRole('option', { name: /محافظة قديمة|Old governorate/ })).toHaveLength(1)
      await user.selectOptions(select, 'g-basra')
      expect(current).toBeDisabled() // moved away: not a destination any more
      expect(within(select).getByRole('option', { name: /البصرة|Basra/ })).toBeEnabled()
    })

    it('saving other edits does not resend an untouched deactivated governorate; moving away sends the new one', async () => {
      vi.mocked(realEstateApi.updateMyListing).mockResolvedValue(ownerListing('d-1', 'Renamed'))
      const { user, form } = await openEditor(ownerListing('d-1', 'Draft', { governorate: retired }))
      const title = within(form).getByLabelText(/عنوان الإعلان|listing title/i)
      await user.clear(title)
      await user.type(title, 'Renamed')
      await user.click(within(form).getByRole('button', { name: /حفظ الإعلان|save listing/i }))
      await waitFor(() => expect(realEstateApi.updateMyListing).toHaveBeenCalledTimes(1))
      expect(vi.mocked(realEstateApi.updateMyListing).mock.calls[0]![1]).not.toHaveProperty('governorate')
      expect(vi.mocked(realEstateApi.updateMyListing).mock.calls[0]![1]).toMatchObject({ title: 'Renamed' })

      // a successful save closes the editor; reopen it and move to an active governorate
      await waitFor(() => expect(screen.getByRole('heading', { name: /إعلان جديد|new listing/i })).toBeInTheDocument())
      const row = (await screen.findAllByTestId('owner-listing'))[0]!
      await user.click(within(row).getByRole('button', { name: EDIT }))
      const reopened = await screen.findByTestId('listing-form')
      await user.selectOptions(within(reopened).getByLabelText(/^المحافظة|^governorate/i), 'g-basra')
      await user.click(within(reopened).getByRole('button', { name: /حفظ الإعلان|save listing/i }))
      await waitFor(() => expect(realEstateApi.updateMyListing).toHaveBeenCalledTimes(2))
      expect(vi.mocked(realEstateApi.updateMyListing).mock.calls[1]![1]).toMatchObject({ governorate: 'g-basra' })
      expect(vi.mocked(realEstateApi.updateMyListing).mock.calls[1]![1]).not.toHaveProperty('city') // it had none: nothing to clear
    })

    it('clears the city when the governorate changes, so a city of another governorate is never sent', async () => {
      vi.mocked(realEstateApi.updateMyListing).mockResolvedValue(ownerListing('d-1', 'Draft'))
      const { user, form } = await openEditor(ownerListing('d-1', 'Draft', { city: karrada }))
      await user.selectOptions(within(form).getByLabelText(/^المحافظة|^governorate/i), 'g-basra')
      expect(within(form).getByLabelText(/^المدينة|^city/i)).toHaveValue('')
      await user.click(within(form).getByRole('button', { name: /حفظ الإعلان|save listing/i }))
      await waitFor(() => expect(realEstateApi.updateMyListing).toHaveBeenCalled())
      expect(vi.mocked(realEstateApi.updateMyListing).mock.calls[0]![1]).toMatchObject({ governorate: 'g-basra', city: null })
    })

    it('adds no duplicate option while the governorate is still active', async () => {
      const { form } = await openEditor(ownerListing('d-1', 'Draft', { governorate: baghdad }))
      const select = within(form).getByLabelText(/^المحافظة|^governorate/i)
      expect(select).toHaveValue('g-baghdad')
      expect(within(select).getAllByRole('option', { name: /بغداد|Baghdad/ })).toHaveLength(1)
      expect(within(select).getAllByRole('option')).toHaveLength(3) // placeholder + 2 active
      expect(within(form).queryByText(/لم تعد متاحة|no longer available/)).toBeNull()
    })

    it('keeps a deactivated city selected, once, and disabled after moving away', async () => {
      const retiredCity: City = { id: 'c-retired', governorate: 'g-baghdad', slug: 'old', name_ar: 'مدينة قديمة', name_en: 'Old city' }
      const { user, form } = await openEditor(ownerListing('d-1', 'Draft', { city: retiredCity }))
      const city = within(form).getByLabelText(/^المدينة|^city/i)
      await waitFor(() => expect(referenceApi.listCities).toHaveBeenCalledWith('g-baghdad', expect.anything()))
      await waitFor(() => expect(within(city).getByRole('option', { name: /مدينة قديمة|Old city/ })).toHaveTextContent(/لم تعد متاحة|no longer available/))
      expect(city).toHaveValue('c-retired')
      const current = within(city).getByRole('option', { name: /مدينة قديمة|Old city/ })
      await user.selectOptions(city, 'c-mansour')
      expect(current).toBeDisabled()
    })

    it('does not offer Publish for a listing whose governorate is no longer active', async () => {
      vi.mocked(realEstateApi.listMyListings).mockResolvedValue(page([ownerListing('d-1', 'Draft', { governorate: retired })]))
      renderApp('/real-estate/owner')
      const row = (await screen.findAllByTestId('owner-listing'))[0]!
      expect(within(row).queryByRole('button', { name: PUBLISH })).toBeNull()
      expect(within(row).getByTestId('owner-listing-gaps')).toHaveTextContent(/محافظة متاحة|available governorate/i)
    })
  })

  it('warns that editing a published listing re-checks every requirement and shows the backend refusal on the form', async () => {
    vi.mocked(realEstateApi.updateMyListing).mockRejectedValue(
      new ApiError(400, 'validation_error', 'Validation failed.', { suitable_uses: ['x'] }, { suitable_uses: ['suitable_use_required'] }),
    )
    vi.mocked(realEstateApi.listMyListings).mockResolvedValue(page([ownerListing('a-1', 'Live', { publication_status: 'PUBLISHED', is_public: true })]))
    renderApp('/real-estate/owner')
    const user = userEvent.setup()
    const row = (await screen.findAllByTestId('owner-listing'))[0]!
    await user.click(within(row).getByRole('button', { name: EDIT }))
    const form = await screen.findByTestId('listing-form')
    expect(within(form).getByText(/يُعاد التحقق من جميع شروط النشر|every publication requirement is re-checked/i)).toBeInTheDocument()
    await user.click(within(form).getByRole('checkbox', { name: /عيادة|clinic/i })) // remove the only use
    await user.click(within(form).getByRole('button', { name: /حفظ الإعلان|save listing/i }))
    expect(await within(form).findByText(/اختر استخدامًا طبيًّا مناسبًا|at least one suitable medical use/i)).toBeInTheDocument()
  })

  it('edits the seller profile', async () => {
    vi.mocked(realEstateApi.updateMySeller).mockResolvedValue(seller)
    renderApp('/real-estate/owner')
    const user = userEvent.setup()
    const name = await screen.findByLabelText(/الاسم المعروض|display name/i)
    await user.clear(name)
    await user.type(name, 'New Name')
    await user.click(screen.getByRole('button', { name: /حفظ الملف|save profile/i }))
    await waitFor(() => expect(realEstateApi.updateMySeller).toHaveBeenCalledWith(expect.objectContaining({ display_name: 'New Name' })))
  })
})
