import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as advertisingApi from '../../api/endpoints/advertising'
import * as authApi from '../../api/endpoints/auth'
import * as workspacesApi from '../../api/endpoints/workspaces'
import { tokenStore } from '../../api/tokens'
import type { Workspace, WorkspaceDashboard } from '../../api'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/workspaces')
vi.mock('../../api/endpoints/advertising')

const ws = (id: string, kind: Workspace['kind'], title: string, role: string | null = 'OWNER'): Workspace => ({
  id, org_id: kind === 'company' || kind === 'facility' ? id.split(':')[1]! : null, team_path: null,
  kind, subtype: '', title, role, path: '/dashboard', verification_status: '', modules: [], capabilities: [],
})

const dashboard = (id: string, kind: Workspace['kind'], title: string, modules: WorkspaceDashboard['modules'], role = 'OWNER'): WorkspaceDashboard => ({
  workspace: { id, kind, subtype: '', title, role, verification_status: '', org_id: null },
  header: { name: 'Demo Person', since: '2026-01-01', reservations_enabled: true },
  actions: [{ key: 'store', path: '/store' }],
  modules,
  generated_at: '2026-10-31T00:00:00Z',
})

const mod = (key: string, stats: [string, number | string | boolean][] = [], variant = '') => ({
  key, variant, link: '', items: [], stats: stats.map(([k, value]) => ({ key: k, value })),
})

beforeEach(() => {
  vi.resetAllMocks()
  tokenStore.set({ access: 'a', refresh: 'r' })
  vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PATIENT' }))
})

describe('workspace dashboard', () => {
  it('renders exactly the modules the server composed, with labelled real figures', async () => {
    vi.mocked(workspacesApi.listWorkspaces).mockResolvedValue([ws('personal', 'patient', 'Me')])
    vi.mocked(workspacesApi.getWorkspaceDashboard).mockResolvedValue(
      dashboard('personal', 'patient', 'Me', [mod('my_orders', [['open_orders', 2]]), mod('store', [['available_products', 6]])]),
    )
    renderApp('/dashboard')
    expect(await screen.findByTestId('workspace-dashboard-patient')).toBeInTheDocument()
    expect(screen.getByTestId('stat-my_orders-open_orders')).toHaveTextContent(/^[2٢]$/)
    expect(screen.getByRole('heading', { name: 'طلباتي من المتجر' })).toBeInTheDocument()
    expect(screen.queryByTestId('module-campaigns')).toBeNull()
    expect(workspacesApi.getWorkspaceDashboard).toHaveBeenCalledWith(null, expect.anything())
  })

  it('switching workspace reloads for that id and never shows the previous organization', async () => {
    const items = [ws('company:a', 'company', 'Org A', 'STAFF'), ws('company:b', 'company', 'Org B', 'VIEWER')]
    vi.mocked(workspacesApi.listWorkspaces).mockResolvedValue(items)
    const pendingB = deferred<WorkspaceDashboard>()
    vi.mocked(workspacesApi.getWorkspaceDashboard).mockImplementation(async (id) =>
      id === 'company:b' ? pendingB.promise : dashboard('company:a', 'company', 'Org A', [mod('store_orders', [['order_placed', 7]])], 'STAFF'),
    )
    const { router } = renderApp('/dashboard')
    expect(await screen.findByTestId('stat-store_orders-order_placed')).toBeInTheDocument()
    await userEvent.selectOptions(await screen.findByTestId('workspace-switcher'), 'company:b')
    await waitFor(() => expect(router.state.location.search).toBe('?ws=company%3Ab'))
    // while B loads, nothing of A is on screen
    expect(screen.queryByTestId('stat-store_orders-order_placed')).toBeNull()
    expect(screen.queryByText('Org A')).toBeNull()
    await act(async () => pendingB.resolve(dashboard('company:b', 'company', 'Org B', [mod('quote_requests', [['awaiting_reply', 1]])], 'VIEWER')))
    expect(await screen.findByTestId('stat-quote_requests-awaiting_reply')).toBeInTheDocument()
    expect(workspacesApi.getWorkspaceDashboard).toHaveBeenLastCalledWith('company:b', expect.anything())
  })

  it('a forged workspace id shows the server refusal, not data', async () => {
    vi.mocked(workspacesApi.listWorkspaces).mockResolvedValue([ws('personal', 'patient', 'Me')])
    const { ApiError } = await import('../../api/client')
    vi.mocked(workspacesApi.getWorkspaceDashboard).mockRejectedValue(new ApiError(404, 'not_found', 'Workspace not found.'))
    renderApp('/dashboard?ws=company:someone-else')
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByTestId(/workspace-dashboard-/)).toBeNull()
  })

  it('sponsored section appears only when the server includes it, labelled as sponsored', async () => {
    vi.mocked(workspacesApi.listWorkspaces).mockResolvedValue([ws('practitioner:1', 'practitioner', 'Dr. Demo')])
    vi.mocked(workspacesApi.getWorkspaceDashboard).mockResolvedValue(
      dashboard('practitioner:1', 'practitioner', 'Dr. Demo', [mod('profile', [['verification', 'VERIFIED']], 'DOCTOR'), mod('sponsored')]),
    )
    vi.mocked(advertisingApi.listSponsored).mockResolvedValue({
      count: 1, next: null, previous: null,
      results: [{ id: 'c1', sponsored: true, starts_on: '2026-10-01', ends_on: '2026-11-30',
        product: { id: 'p1', title: 'Electric dental chair', price: '9500000.00', currency: 'IQD', brand: '', model_name: '', category: { id: 'x', slug: 'd', name_ar: 'أسنان', name_en: 'Dental' }, company: { id: 'co', name: 'Nakhla' } } } as never],
    })
    renderApp('/dashboard')
    const ad = await screen.findByTestId('sponsored-ad')
    expect(within(ad).getByText('إعلان ممول')).toBeInTheDocument()
    expect(screen.getByTestId('stat-profile-verification')).toHaveTextContent(/موثّق|موثق/)
  })

  it('never shows a previous account’s workspace data after logout and another login', async () => {
    vi.mocked(workspacesApi.listWorkspaces).mockResolvedValue([ws('company:a', 'company', 'Org A', 'STAFF')])
    const late = deferred<WorkspaceDashboard>()
    vi.mocked(workspacesApi.getWorkspaceDashboard).mockReturnValueOnce(late.promise)
    vi.mocked(authApi.logout).mockImplementation(async () => {
      tokenStore.clear()
    })
    const { router } = renderApp('/dashboard')
    await waitFor(() => expect(workspacesApi.getWorkspaceDashboard).toHaveBeenCalledTimes(1))
    await userEvent.click(await screen.findByRole('button', { name: /log out|تسجيل الخروج/i }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    await act(async () =>
      late.resolve(dashboard('company:a', 'company', 'ACCOUNT A ORG', [mod('store_orders', [['order_placed', 9]])], 'STAFF')),
    )
    expect(screen.queryByText('ACCOUNT A ORG')).toBeNull()

    vi.mocked(authApi.login).mockResolvedValue({ access: 'b', refresh: 'b' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ id: '22222222-2222-4222-8222-222222222222' }))
    vi.mocked(workspacesApi.listWorkspaces).mockResolvedValue([ws('personal', 'patient', 'Account B')])
    vi.mocked(workspacesApi.getWorkspaceDashboard).mockResolvedValue(
      dashboard('personal', 'patient', 'Account B', [mod('my_orders', [['open_orders', 1]])]),
    )
    await userEvent.type(screen.getByLabelText(/email|البريد الإلكتروني/i), 'b@example.com')
    await userEvent.type(screen.getByLabelText(/^password$|^كلمة المرور$/i), 'Str0ng-Passw0rd!{Enter}')
    expect(await screen.findByTestId('workspace-dashboard-patient')).toBeInTheDocument()
    expect(screen.queryByText('ACCOUNT A ORG')).toBeNull()
    expect(screen.queryByTestId('stat-store_orders-order_placed')).toBeNull()
  })
})
