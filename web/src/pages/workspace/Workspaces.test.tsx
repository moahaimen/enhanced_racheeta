import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../../api/endpoints/auth'
import * as referenceApi from '../../api/endpoints/reference'
import * as workspacesApi from '../../api/endpoints/workspaces'
import { tokenStore } from '../../api/tokens'
import type { OrgSummary, StoreProduct, Workspace } from '../../api'
import { baghdad } from '../../test/providerFixtures'
import { makeAccount, renderApp } from '../../test/renderApp'
import { cart } from '../store/cart'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/reference')
vi.mock('../../api/endpoints/workspaces')

const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

const product: StoreProduct = {
  id: 'p-1',
  title: 'كرسي متحرك | Folding wheelchair',
  description: '',
  brand: '',
  model_name: '',
  price: '185000.00',
  currency: 'IQD',
  in_stock: true,
  category: { id: 'c-1', slug: 'mobility', name_ar: 'وسائل الحركة', name_en: 'Mobility aids' },
  company: { id: 'm-1', name: 'متجر | Rehab store' },
}

function signIn(role: 'PATIENT' | 'PROVIDER' | 'MEDICAL_COMPANY' = 'PATIENT') {
  tokenStore.set({ access: 'a', refresh: 'r' })
  vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role, email_verified: true }))
}

beforeEach(() => {
  vi.resetAllMocks()
  tokenStore.clear()
  cart.clear()
})

describe('workspace switcher', () => {
  it('lists exactly the workspaces the server returns, with their roles', async () => {
    signIn()
    const items: Workspace[] = [
      { id: 'a', kind: 'patient', subtype: '', title: 'Me', role: null, path: '/dashboard', verification_status: '', modules: [], capabilities: [] },
      { id: 'b', kind: 'facility', subtype: 'HOSPITAL', title: 'مستشفى دجلة | Dijla Hospital', role: 'STAFF', path: '/workspace/facility/b', verification_status: 'VERIFIED', modules: [], capabilities: [] },
    ]
    vi.mocked(workspacesApi.listWorkspaces).mockResolvedValue(items)
    renderApp('/workspaces')
    const list = await screen.findByTestId('workspace-list')
    expect(within(list).getByText('مستشفى دجلة')).toBeInTheDocument()
    expect(within(list).getByText(/موظف/)).toBeInTheDocument()
    const links = within(list).getAllByRole('link', { name: /^فتح$/ })
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/dashboard', '/workspace/facility/b'])
  })
})

describe('organization workspace', () => {
  const summary = (capabilities: string[], role: OrgSummary['role']): OrgSummary => ({
    id: 'fac-1',
    name: 'Dijla Hospital',
    role,
    capabilities,
    counts: { pending: 1, upcoming: 2, today: 0, practitioners: 3, staff: 2 },
  })

  it('a viewer sees reservations but no action buttons and no team panel', async () => {
    signIn()
    vi.mocked(workspacesApi.getOrgSummary).mockResolvedValue(summary(['facility.view', 'facility.reservations.view'], 'VIEWER'))
    vi.mocked(workspacesApi.listFacilityReservations).mockResolvedValue(
      page([
        {
          id: 'r-1', status: 'PENDING', service_title_snapshot: 'Consultation', starts_at: '2026-11-02T09:00:00Z',
          patient: { id: 'x', full_name: 'Demo patient' },
        } as never,
      ]),
    )
    renderApp('/workspace/facility/fac-1')
    expect(await screen.findByTestId('facility-reservations')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /مؤكد|confirmed/i })).toBeNull()
    expect(screen.queryByTestId('org-members')).toBeNull()
    expect(workspacesApi.listOrgMembers).not.toHaveBeenCalled()
  })

  it('staff with manage capability can confirm through the server', async () => {
    signIn()
    vi.mocked(workspacesApi.getOrgSummary).mockResolvedValue(
      summary(['facility.view', 'facility.reservations.view', 'facility.reservations.manage'], 'STAFF'),
    )
    vi.mocked(workspacesApi.listFacilityReservations).mockResolvedValue(
      page([{ id: 'r-1', status: 'PENDING', service_title_snapshot: 'Consultation', starts_at: '2026-11-02T09:00:00Z', patient: { id: 'x', full_name: 'P' } } as never]),
    )
    vi.mocked(workspacesApi.transitionFacilityReservation).mockResolvedValue({} as never)
    renderApp('/workspace/facility/fac-1')
    await userEvent.click(await screen.findByRole('button', { name: /^مؤكد$/ }))
    await waitFor(() => expect(workspacesApi.transitionFacilityReservation).toHaveBeenCalledWith('fac-1', 'r-1', 'CONFIRMED'))
  })
})

describe('store and checkout', () => {
  it('sends only product ids and quantities; the server computes the total', async () => {
    signIn()
    vi.mocked(workspacesApi.listStoreCategories).mockResolvedValue([product.category])
    vi.mocked(workspacesApi.listStoreProducts).mockResolvedValue(page([product]))
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad])
    vi.mocked(workspacesApi.placeOrder).mockResolvedValue({ id: 'o-1', number: 'RCH-1' } as never)
    const { router } = renderApp('/store')
    await userEvent.click(await screen.findByTestId('add-p-1'))
    await router.navigate('/cart')
    const form = await screen.findByTestId('checkout-form')
    await userEvent.selectOptions(await within(form).findByLabelText(/المحافظة|governorate/i), baghdad.id)
    await userEvent.type(within(form).getByLabelText(/عنوان التوصيل|delivery address/i), 'Demo street')
    await userEvent.type(within(form).getByLabelText(/رقم التواصل|contact phone/i), '07700000000')
    await userEvent.click(within(form).getByRole('button', { name: /تأكيد الطلب|place order/i }))
    await waitFor(() => expect(workspacesApi.placeOrder).toHaveBeenCalledTimes(1))
    const payload = vi.mocked(workspacesApi.placeOrder).mock.calls[0]![0]
    expect(payload.items).toEqual([{ product: 'p-1', quantity: 1 }])
    expect(JSON.stringify(payload)).not.toMatch(/price|total|card/i)
    expect(payload.payment_method).toBe('CASH_ON_DELIVERY')
    expect(await screen.findByText(/RCH-1/)).toBeInTheDocument()
  })

  it('states that the demo never collects card data', async () => {
    vi.mocked(workspacesApi.listStoreCategories).mockResolvedValue([])
    vi.mocked(workspacesApi.listStoreProducts).mockResolvedValue(page([]))
    renderApp('/store')
    expect(await screen.findByText(/لا تُجمع بيانات بطاقات|no card data/i)).toBeInTheDocument()
  })
})

describe('preferences', () => {
  it('keeps display separate from outreach and saves one switch at a time', async () => {
    signIn('PROVIDER')
    const prefs = {
      show_sponsored_products: true, real_estate_promotions: false, job_alerts: false, offers_and_news: false,
      channel_in_app: true, channel_email: false, channel_push: false,
    }
    vi.mocked(workspacesApi.getPreferences).mockResolvedValue(prefs)
    vi.mocked(workspacesApi.updatePreferences).mockResolvedValue({ ...prefs, real_estate_promotions: true })
    renderApp('/settings/preferences')
    const realEstate = await screen.findByTestId('pref-real_estate_promotions')
    expect(realEstate).not.toBeChecked()
    expect(screen.getByTestId('pref-channel_email')).toBeDisabled()
    await userEvent.click(realEstate)
    await waitFor(() => expect(workspacesApi.updatePreferences).toHaveBeenCalledWith({ real_estate_promotions: true }))
  })
})
