import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as jobsApi from '../../api/endpoints/jobs'
import { tokenStore } from '../../api/tokens'
import { makeEmployerPublic, makeJobCard, paginated } from '../../test/jobFixtures'
import { deferred, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/jobs')
vi.mock('../../api/endpoints/reference')

const jobsPage = (page: number, size = 20) =>
  paginated(
    Array.from({ length: size }, (_, i) => makeJobCard({ id: `j-${page}-${i}`, title: `Job ${page}-${i}` })),
    45,
    page < 3 ? 'n' : null,
    page > 1 ? 'p' : null,
  )

describe('EmployerPublicPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
    vi.mocked(jobsApi.getEmployerPublic).mockResolvedValue(makeEmployerPublic({ description: 'مستشفى عام.' }))
  })

  it('renders the employer header and the first page of published jobs', async () => {
    vi.mocked(jobsApi.listJobs).mockImplementation((params = {}) => Promise.resolve(jobsPage(params.page ?? 1)))
    renderApp('/employers/e-1')
    expect(await screen.findByRole('heading', { level: 1, name: 'مستشفى الأمل' })).toBeInTheDocument()
    expect(screen.getAllByText(/جهة موثّقة|Verified employer/i).length).toBeGreaterThan(0)
    expect(screen.getByText('مستشفى عام.')).toBeInTheDocument()
    expect(await screen.findByText('Job 1-0')).toBeInTheDocument()
    expect(jobsApi.listJobs).toHaveBeenCalledWith(expect.objectContaining({ employer: 'e-1', page: 1 }), expect.anything())
    expect(screen.getByTestId('employer-jobs-count')).toHaveTextContent(/45/)
    expect(screen.getByText(/صفحة 1 من 3|Page 1 of 3/)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/@|\+964/)
  })

  it('reads ?jobs_page=2 from the URL and sends it to the API', async () => {
    vi.mocked(jobsApi.listJobs).mockImplementation((params = {}) => Promise.resolve(jobsPage(params.page ?? 1)))
    renderApp('/employers/e-1?jobs_page=2')
    expect(await screen.findByText('Job 2-0')).toBeInTheDocument()
    expect(jobsApi.listJobs).toHaveBeenCalledWith(expect.objectContaining({ employer: 'e-1', page: 2 }), expect.anything())
  })

  it('moves with next and previous, keeping the header while the jobs block shows its loading state', async () => {
    const second = deferred<ReturnType<typeof jobsPage>>()
    vi.mocked(jobsApi.listJobs).mockImplementation((params = {}) => {
      if (params.page === 2) return second.promise
      return Promise.resolve(jobsPage(params.page ?? 1))
    })
    const { router } = renderApp('/employers/e-1')
    expect(await screen.findByText('Job 1-0')).toBeInTheDocument()
    const user = userEvent.setup({ delay: null })
    await user.click(screen.getByRole('button', { name: /التالي|Next/i }))
    await waitFor(() => expect(router.state.location.search).toBe('?jobs_page=2'))
    expect(await screen.findByTestId('employer-jobs-loading')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'مستشفى الأمل' })).toBeInTheDocument() // header stays mounted
    expect(jobsApi.getEmployerPublic).toHaveBeenCalledTimes(1)
    second.resolve(jobsPage(2))
    expect(await screen.findByText('Job 2-0')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /السابق|Previous/i }))
    await waitFor(() => expect(router.state.location.search).toBe(''))
    expect(await screen.findByText('Job 1-0')).toBeInTheDocument()
  })

  it('handles an empty final page with a way back, and an employer without jobs', async () => {
    vi.mocked(jobsApi.listJobs).mockResolvedValue({ count: 40, next: null, previous: 'p', results: [] })
    renderApp('/employers/e-1?jobs_page=3')
    const empty = await screen.findByTestId('employer-jobs-empty-page')
    expect(within(empty).getByRole('link')).toHaveAttribute('href', '/employers/e-1')
    vi.mocked(jobsApi.listJobs).mockResolvedValue(paginated([]))
    renderApp('/employers/e-1')
    expect(await screen.findByTestId('employer-jobs-empty')).toBeInTheDocument()
  })

  it('shows the not-found state for an unknown employer', async () => {
    vi.mocked(jobsApi.getEmployerPublic).mockRejectedValue(new ApiError(404, 'not_found', 'missing'))
    renderApp('/employers/nope')
    expect(await screen.findByText(/غير موجودة|not found|no longer available/i)).toBeInTheDocument()
    expect(jobsApi.listJobs).not.toHaveBeenCalled()
  })
})
