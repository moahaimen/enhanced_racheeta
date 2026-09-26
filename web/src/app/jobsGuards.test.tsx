import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as adminApi from '../api/endpoints/admin'
import * as authApi from '../api/endpoints/auth'
import * as jobsApi from '../api/endpoints/jobs'
import * as referenceApi from '../api/endpoints/reference'
import { tokenStore } from '../api/tokens'
import { paginated } from '../test/jobFixtures'
import { baghdad } from '../test/providerFixtures'
import { makeAccount, renderApp } from '../test/renderApp'

vi.mock('../api/endpoints/auth')
vi.mock('../api/endpoints/jobs')
vi.mock('../api/endpoints/admin')
vi.mock('../api/endpoints/reference')

describe('Phase 3 routes and guards', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad])
    vi.mocked(referenceApi.listSpecialties).mockResolvedValue([])
    vi.mocked(jobsApi.listJobs).mockResolvedValue(paginated([]))
    vi.mocked(adminApi.listEmployers).mockResolvedValue(paginated([]))
  })

  it('serves the public jobs search to anonymous visitors', async () => {
    renderApp('/jobs')
    expect(await screen.findByRole('heading', { level: 1, name: /فرص العمل|Jobs in the medical/i })).toBeInTheDocument()
    expect(jobsApi.listJobs).toHaveBeenCalled()
  })

  it.each(['/jobs/profile', '/jobs/my-applications', '/employer', '/employer/talent', '/admin-console'])('sends anonymous visitors from %s to /login and remembers the target', async (path) => {
    const { router } = renderApp(path)
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.state).toEqual({ from: path })
  })

  it('denies the admin console to a signed-in non-staff account', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ is_staff: false }))
    renderApp('/admin-console')
    expect(await screen.findByTestId('staff-denied')).toBeInTheDocument()
    expect(adminApi.listEmployers).not.toHaveBeenCalled()
  })

  it('renders the admin console for a staff account and links it from the header', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ is_staff: true }))
    renderApp('/admin-console')
    expect(await screen.findByRole('heading', { level: 1, name: /لوحة الإدارة|Admin console/i })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /لوحة الإدارة|Admin console/i }).length).toBeGreaterThan(0)
    await waitFor(() => expect(adminApi.listEmployers).toHaveBeenCalled())
  })

  it('always shows the Jobs link in the header and never the admin link to non-staff', async () => {
    renderApp('/jobs')
    expect((await screen.findAllByRole('link', { name: /الوظائف|Jobs/ })).length).toBeGreaterThan(0)
    expect(screen.queryByRole('link', { name: /لوحة الإدارة|Admin console/i })).toBeNull()
  })
})
