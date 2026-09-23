import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as jobsApi from '../../api/endpoints/jobs'
import * as referenceApi from '../../api/endpoints/reference'
import { tokenStore } from '../../api/tokens'
import { makeJobCard, paginated } from '../../test/jobFixtures'
import { baghdad, basra, cardiology } from '../../test/providerFixtures'
import { deferred, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/jobs')
vi.mock('../../api/endpoints/reference')

describe('JobsPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad, basra])
    vi.mocked(referenceApi.listSpecialties).mockResolvedValue([cardiology])
    vi.mocked(referenceApi.listCities).mockResolvedValue([])
  })

  it('shows skeletons, then job cards with employer, profession and location', async () => {
    const pending = deferred<ReturnType<typeof paginated<ReturnType<typeof makeJobCard>>>>()
    vi.mocked(jobsApi.listJobs).mockReturnValue(pending.promise)
    renderApp('/jobs')
    expect(screen.getAllByTestId('async-loading').length).toBeGreaterThan(0)
    pending.resolve(paginated([makeJobCard(), makeJobCard({ id: 'j-2', title: 'صيدلاني', profession: 'PHARMACIST', is_featured: true })]))
    expect(await screen.findByRole('link', { name: 'ممرض قسم الطوارئ' })).toHaveAttribute('href', '/jobs/j-1')
    expect(screen.getByRole('link', { name: 'صيدلاني' })).toBeInTheDocument()
    expect(screen.getByTestId('jobs-count')).toHaveTextContent(/وظيفتان|2 jobs/)
    expect(screen.getAllByText('مستشفى الأمل').length).toBeGreaterThan(0)
    // Public cards never carry contact data.
    expect(document.body.textContent).not.toMatch(/@|\+964/)
  })

  it('reads filters from the URL and pushes filter changes back into it', async () => {
    vi.mocked(jobsApi.listJobs).mockResolvedValue(paginated([]))
    const { router } = renderApp('/jobs?profession=NURSE&governorate=g-basra')
    expect(await screen.findByTestId('jobs-empty')).toBeInTheDocument()
    expect(jobsApi.listJobs).toHaveBeenLastCalledWith(expect.objectContaining({ profession: 'NURSE', governorate: 'g-basra' }), expect.anything())

    const user = userEvent.setup()
    await user.selectOptions(await screen.findByLabelText(/نوع الدوام|Employment type/i), 'PART_TIME')
    await waitFor(() => expect(router.state.location.search).toContain('employment_type=PART_TIME'))
    await waitFor(() => expect(jobsApi.listJobs).toHaveBeenLastCalledWith(expect.objectContaining({ employment_type: 'PART_TIME', profession: 'NURSE' }), expect.anything()))
  })

  it('submits the free-text search on enter', async () => {
    vi.mocked(jobsApi.listJobs).mockResolvedValue(paginated([]))
    const { router } = renderApp('/jobs')
    await screen.findByTestId('jobs-empty')
    const user = userEvent.setup()
    await user.type(screen.getByRole('searchbox'), 'طوارئ{enter}')
    await waitFor(() => expect(router.state.location.search).toContain('q='))
    await waitFor(() => expect(jobsApi.listJobs).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'طوارئ' }), expect.anything()))
  })
})
