import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../api/endpoints/auth'
import * as jobsApi from '../api/endpoints/jobs'
import * as marketplaceApi from '../api/endpoints/marketplace'
import * as providersApi from '../api/endpoints/providers'
import * as realEstateApi from '../api/endpoints/realEstate'
import * as referenceApi from '../api/endpoints/reference'
import { tokenStore } from '../api/tokens'
import type { PropertyListing } from '../api'
import { CountUp, NearViewport, Reveal } from '../design-system'
import { changeLanguage } from '../i18n'
import { makeJobCard, paginated } from '../test/jobFixtures'
import { baghdad, cardiology, makeCard } from '../test/providerFixtures'
import { emptyPage, mockHomeData } from '../test/homeMocks'
import { makeAccount, renderApp } from '../test/renderApp'

vi.mock('../api/endpoints/auth')
vi.mock('../api/endpoints/providers')
vi.mock('../api/endpoints/reference')
vi.mock('../api/endpoints/jobs')
vi.mock('../api/endpoints/realEstate')
vi.mock('../api/endpoints/marketplace')

const listing = (overrides: Partial<PropertyListing> = {}): PropertyListing => ({
  id: 'l-1',
  title: 'عيادة جاهزة | Fitted clinic',
  description: '',
  property_type: 'CLINIC',
  transaction_type: 'RENT',
  governorate: baghdad,
  city: null,
  district: 'المنصور',
  latitude: null,
  longitude: null,
  area_sqm: '95.00',
  price: '2500000.00',
  currency: 'IQD',
  suitable_uses: ['CLINIC'],
  facilities: '',
  contact_method: 'PHONE',
  contact_phone: null,
  contact_email: null,
  seller: { id: 's-1', display_name: 'Seller', seller_type: 'AGENT' },
  published_at: '2026-10-01T10:00:00Z',
  expires_at: '2026-12-01T10:00:00Z',
  created_at: '2026-10-01T10:00:00Z',
  updated_at: '2026-10-01T10:00:00Z',
  ...overrides,
})

beforeEach(async () => {
  vi.resetAllMocks()
  tokenStore.clear()
  await changeLanguage('ar')
  mockHomeData()
  vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad])
})

describe('premium homepage — search', () => {
  it('routes a doctor search to the providers list as kind=PRACTITIONER with the typed name and governorate', async () => {
    const user = userEvent.setup()
    const { router } = renderApp('/')
    const form = await screen.findByRole('form', { name: /ابحث في رشيتة/ })
    await waitFor(() => expect(within(form).getByRole('option', { name: /بغداد/ })).toBeInTheDocument())
    await user.selectOptions(within(form).getByRole('combobox'), 'g-baghdad')
    await user.type(within(form).getByRole('searchbox'), 'كريم')
    await user.click(within(form).getByRole('button', { name: /^بحث$/ }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/providers'))
    const params = new URLSearchParams(router.state.location.search)
    expect(params.get('kind')).toBe('PRACTITIONER')
    expect(params.get('search')).toBe('كريم')
    expect(params.get('governorate')).toBe('g-baghdad')
  })

  it('routes the facilities, jobs and real-estate tabs to the existing, backend-filtered searches', async () => {
    for (const [tab, path, key] of [
      [/المستشفيات والمراكز/, '/providers', 'search'],
      [/^الوظائف$/, '/jobs', 'q'],
      [/^العقارات$/, '/real-estate', 'search'],
    ] as const) {
      const user = userEvent.setup()
      const { router, unmount } = renderApp('/')
      const form = await screen.findByRole('form', { name: /ابحث في رشيتة/ })
      await user.click(within(form).getByRole('radio', { name: tab }))
      await user.type(within(form).getByRole('searchbox'), 'نص')
      await user.click(within(form).getByRole('button', { name: /^بحث$/ }))
      await waitFor(() => expect(router.state.location.pathname).toBe(path))
      const params = new URLSearchParams(router.state.location.search)
      expect(params.get(key)).toBe('نص')
      if (path === '/providers') expect(params.get('kind')).toBe('FACILITY')
      unmount()
    }
  })

  it('searches with no text and no governorate without inventing parameters', async () => {
    const user = userEvent.setup()
    const { router } = renderApp('/')
    const form = await screen.findByRole('form', { name: /ابحث في رشيتة/ })
    await user.click(within(form).getByRole('radio', { name: /^الوظائف$/ }))
    await user.click(within(form).getByRole('button', { name: /^بحث$/ }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/jobs'))
    expect(router.state.location.search).toBe('')
  })
})

describe('premium homepage — sections come from the API (nothing hard-coded)', () => {
  it('shows verified doctors from the providers API, best rated first, with a booking call to action', async () => {
    vi.mocked(providersApi.listProviders).mockImplementation(async (params) =>
      params?.kind === 'PRACTITIONER'
        ? paginated([
            makeCard({ id: 'p-low', display_name: 'د. منخفض | Dr Low', average_rating: 3.9, review_count: 4 }),
            makeCard({ id: 'p-top', display_name: 'د. أعلى | Dr Top', average_rating: 4.9, review_count: 8, specialties: [cardiology] }),
            makeCard({ id: 'p-new', display_name: 'د. جديد | Dr New' }),
          ])
        : emptyPage,
    )
    renderApp('/')
    const grid = await screen.findByTestId('featured-doctors')
    const links = within(grid).getAllByRole('link')
    expect(links.map((a) => a.textContent)).toEqual(['د. أعلى', 'د. منخفض', 'د. جديد']) // Arabic half only; sorted by rating
    expect(links[0]).toHaveAttribute('href', '/providers/p-top')
    expect(within(grid).getAllByText(/احجز الآن/)).toHaveLength(3)
    expect(within(grid).getByText('4.9')).toBeInTheDocument()
    expect(within(grid).getAllByText('أمراض القلب').length).toBeGreaterThanOrEqual(1)
    expect(vi.mocked(providersApi.listProviders)).toHaveBeenCalledWith(expect.objectContaining({ kind: 'PRACTITIONER' }), expect.anything())
  })

  it('shows the English half of "Arabic | English" names when the UI is English', async () => {
    await changeLanguage('en')
    vi.mocked(providersApi.listProviders).mockImplementation(async (params) =>
      params?.kind === 'PRACTITIONER' ? paginated([makeCard({ display_name: 'د. أعلى | Dr Top' })]) : emptyPage,
    )
    renderApp('/')
    const grid = await screen.findByTestId('featured-doctors')
    expect(within(grid).getByRole('link', { name: 'Dr Top' })).toBeInTheDocument()
  })

  it('keeps a graceful empty state when there are no doctors', async () => {
    renderApp('/')
    expect(await screen.findByTestId('featured-empty')).toBeInTheDocument()
    expect(screen.queryByTestId('featured-doctors')).toBeNull()
  })

  it('lists facilities, latest jobs and latest properties from their own public endpoints', async () => {
    vi.mocked(providersApi.listProviders).mockImplementation(async (params) =>
      params?.kind === 'FACILITY' ? paginated([makeCard({ id: 'f-1', kind: 'FACILITY', provider_type: 'HOSPITAL', display_name: 'مستشفى دجلة | Dijla Hospital' })]) : emptyPage,
    )
    vi.mocked(jobsApi.listJobs).mockResolvedValue(paginated([makeJobCard({ id: 'j-9', title: 'طبيب عام | General Practitioner' })]))
    vi.mocked(realEstateApi.listListings).mockResolvedValue(paginated([listing()]))
    renderApp('/')
    const facilities = await screen.findByTestId('facilities')
    expect(within(facilities).getByRole('link', { name: 'مستشفى دجلة' })).toHaveAttribute('href', '/providers/f-1')
    const jobs = await screen.findByTestId('latest-jobs')
    expect(within(jobs).getByRole('link', { name: 'طبيب عام' })).toHaveAttribute('href', '/jobs/j-9')
    const properties = await screen.findByTestId('latest-properties')
    const card = within(properties).getByRole('link', { name: 'عيادة جاهزة' })
    expect(card).toHaveAttribute('href', '/real-estate/l-1')
    expect(properties).toHaveTextContent('2,500,000')
    expect(properties).toHaveTextContent('IQD')
  })

  it('shows only REAL platform numbers and omits a stat whose list is empty', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue({ ...emptyPage, count: 36 })
    vi.mocked(jobsApi.listJobs).mockResolvedValue({ ...emptyPage, count: 21 })
    vi.mocked(marketplaceApi.listCategories).mockResolvedValue([])
    renderApp('/')
    const stats = await screen.findByTestId('platform-stats')
    expect(within(stats).getByText(/مقدّم خدمة موثّق/)).toBeInTheDocument()
    expect(within(stats).getByText(/وظيفة منشورة/)).toBeInTheDocument()
    expect(within(stats).queryByText(/عقار طبي/)).toBeNull() // zero listings: not shown
    expect(within(stats).queryByText(/فئة منتجات/)).toBeNull()
    expect(within(stats).getByLabelText('36')).toBeInTheDocument()
  })
})

describe('premium homepage — suppliers, products and roles', () => {
  it('shows anonymous visitors the public product categories (real reference data), not products', async () => {
    vi.mocked(marketplaceApi.listCategories).mockResolvedValue([
      { id: 'c-1', slug: 'diagnostic-devices', name_ar: 'أجهزة التشخيص', name_en: 'Diagnostic devices', parent_id: null, sort_order: 1, can_publish: true },
    ])
    renderApp('/')
    const chips = await screen.findByTestId('product-categories')
    expect(within(chips).getByText('أجهزة التشخيص')).toBeInTheDocument()
    expect(marketplaceApi.listTargetedProducts).not.toHaveBeenCalled()
    expect(screen.queryByTestId('home-products')).toBeNull()
  })

  it('shows a signed-in provider the products the backend targets at their profile', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PROVIDER' }))
    vi.mocked(marketplaceApi.listTargetedProducts).mockResolvedValue(
      paginated([
        {
          id: 'prod-1',
          title: 'جهاز تخطيط القلب | ECG machine',
          description: '',
          brand: 'Sharq',
          model_name: 'ECG-12',
          price: '2850000.00',
          currency: 'IQD',
          category: { id: 'c-1', slug: 'dx', name_ar: 'أجهزة التشخيص', name_en: 'Diagnostic devices', parent_id: null, sort_order: 1, can_publish: true },
          company: { id: 'co-1', name: 'الشرق | Al-Sharq', verification_status: 'VERIFIED' } as never,
          created_at: '',
          updated_at: '',
        },
      ]),
    )
    renderApp('/')
    const products = await screen.findByTestId('home-products')
    expect(within(products).getByRole('link', { name: 'جهاز تخطيط القلب' })).toHaveAttribute('href', '/marketplace/products/prod-1')
    expect(products).toHaveTextContent('2,850,000')
    expect(screen.queryByTestId('product-categories')).toBeNull()
  })

  it('offers the supplier shortcut to anonymous visitors, providers and companies — never to a patient or seller', async () => {
    const supplierLinks = () =>
      screen
        .getAllByRole('link')
        .filter((a) => ['/marketplace', '/company'].includes(a.getAttribute('href') ?? ''))
    const anonymous = renderApp('/')
    await screen.findByTestId('platform-stats').catch(() => undefined)
    await screen.findByRole('navigation', { name: /تصفّح حسب الفئة|browse by category/i })
    expect(supplierLinks().some((a) => a.getAttribute('href') === '/marketplace')).toBe(true)
    anonymous.unmount()

    for (const role of ['PATIENT', 'REAL_ESTATE_SELLER'] as const) {
      vi.resetAllMocks()
      mockHomeData()
      tokenStore.set({ access: 'a', refresh: 'r' })
      vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role }))
      const view = renderApp('/')
      await screen.findAllByRole('link', { name: /لوحة المعلومات|dashboard/i })
      expect(supplierLinks()).toHaveLength(0)
      view.unmount()
    }
  })
})

describe('premium homepage — navigation', () => {
  it('adds a Hospitals & centers entry that is active only on ?kind=FACILITY', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue(emptyPage)
    const { router } = renderApp('/providers?kind=FACILITY')
    const facilities = await screen.findAllByRole('link', { name: /المستشفيات والمراكز/ })
    const navEntry = facilities.find((a) => a.getAttribute('href') === '/providers?kind=FACILITY' && a.className.includes('link'))!
    expect(navEntry).toHaveAttribute('aria-current', 'page')
    const providersEntry = screen.getAllByRole('link', { name: /^مقدّمو الخدمات$/ })[0]!
    expect(providersEntry).not.toHaveAttribute('aria-current')
    await act(async () => {
      await router.navigate('/providers')
    })
    await waitFor(() => expect(screen.getAllByRole('link', { name: /^مقدّمو الخدمات$/ })[0]).toHaveAttribute('aria-current', 'page'))
  })
})

describe('Cairo and design tokens', () => {
  it('self-hosts Cairo: no third-party font request anywhere in the entry points', () => {
    const html = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8')
    expect(html).not.toMatch(/fonts\.googleapis|fonts\.gstatic/)
    const main = readFileSync(resolve(process.cwd(), 'src/main.tsx'), 'utf8')
    expect(main).toContain("@fontsource-variable/cairo/wght.css")
    const pkg = JSON.parse(readFileSync(resolve(process.cwd(), 'package.json'), 'utf8')) as { dependencies: Record<string, string> }
    expect(pkg.dependencies['@fontsource-variable/cairo']).toMatch(/^\d/) // pinned exactly
  })
})

describe('motion primitives degrade safely', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows content immediately where IntersectionObserver does not exist', () => {
    render(
      <Reveal>
        <NearViewport>
          <p>content</p>
        </NearViewport>
      </Reveal>,
    )
    expect(screen.getByText('content')).toBeInTheDocument()
  })

  it('mounts a lazy block only when it nears the viewport', () => {
    const observers: { cb: IntersectionObserverCallback }[] = []
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        constructor(cb: IntersectionObserverCallback) {
          observers.push({ cb })
        }
        observe() {}
        disconnect() {}
      },
    )
    render(
      <NearViewport>
        <p>below the fold</p>
      </NearViewport>,
    )
    expect(screen.queryByText('below the fold')).toBeNull()
    act(() => observers[0]!.cb([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver))
    expect(screen.getByText('below the fold')).toBeInTheDocument()
  })

  it('still reveals content if the observer never reports (scroll fail-safe)', async () => {
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        observe() {}
        disconnect() {}
      },
    )
    const rect = vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({ top: 100, bottom: 200, left: 0, right: 10, width: 10, height: 100, x: 0, y: 100, toJSON() {} })
    render(
      <NearViewport>
        <p>fail-safe content</p>
      </NearViewport>,
    )
    await waitFor(() => expect(screen.getByText('fail-safe content')).toBeInTheDocument())
    rect.mockRestore()
  })

  it('counts up to a real value, and shows it at once under prefers-reduced-motion', () => {
    vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('reduce'), media: query, addEventListener() {}, removeEventListener() {} }))
    render(<CountUp value={1234} locale="en" />)
    expect(screen.getByLabelText('1,234')).toHaveTextContent('1,234')
  })
})
