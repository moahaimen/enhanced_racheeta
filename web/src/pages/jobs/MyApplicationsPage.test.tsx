import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as jobsApi from '../../api/endpoints/jobs'
import { tokenStore } from '../../api/tokens'
import { makeApplicationSeeker, makeJobCard, paginated } from '../../test/jobFixtures'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/jobs')
vi.mock('../../api/endpoints/reference')

describe('MyApplicationsPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount())
    vi.mocked(jobsApi.listMyInvitations).mockResolvedValue(paginated([]))
    vi.mocked(jobsApi.listMessages).mockResolvedValue([])
  })

  it('shows an empty state with a link to the jobs search', async () => {
    vi.mocked(jobsApi.listMyApplications).mockResolvedValue(paginated([]))
    renderApp('/jobs/my-applications')
    const empty = await screen.findByTestId('applications-empty')
    expect(within(empty).getByRole('link', { name: /تصفّح الوظائف|Browse jobs/i })).toHaveAttribute('href', '/jobs')
  })

  it('lists applications with status and withdraws one', async () => {
    vi.mocked(jobsApi.listMyApplications).mockResolvedValueOnce(paginated([makeApplicationSeeker()])).mockResolvedValueOnce(paginated([makeApplicationSeeker({ status: 'WITHDRAWN' })]))
    vi.mocked(jobsApi.withdrawApplication).mockResolvedValue(makeApplicationSeeker({ status: 'WITHDRAWN' }))
    renderApp('/jobs/my-applications')
    const card = await screen.findByTestId('application-card')
    expect(within(card).getAllByText(/مُقدَّم|Submitted/).length).toBeGreaterThan(0)
    const user = userEvent.setup()
    await user.click(within(card).getByRole('button', { name: /سحب الطلب|Withdraw/i }))
    expect(jobsApi.withdrawApplication).toHaveBeenCalledWith('a-1')
    await waitFor(() => expect(jobsApi.listMyApplications).toHaveBeenCalledTimes(2))
    expect((await screen.findAllByText(/مسحوب|Withdrawn/)).length).toBeGreaterThan(0)
  })

  it('sends a message in the thread and surfaces the contact-blocking error', async () => {
    vi.mocked(jobsApi.listMyApplications).mockResolvedValue(paginated([makeApplicationSeeker({ status: 'REVIEWING' })]))
    vi.mocked(jobsApi.sendMessage).mockRejectedValue(
      new ApiError(400, 'validation_error', 'Validation failed.', { body: ['Contact information is not allowed.'] }, { body: ['contact_information_not_allowed'] }),
    )
    renderApp('/jobs/my-applications')
    const thread = await screen.findByTestId('messages-thread')
    const user = userEvent.setup()
    await user.type(within(thread).getByRole('textbox'), 'واتساب 07701234567')
    await user.click(within(thread).getByRole('button', { name: /إرسال|Send/i }))
    expect(jobsApi.sendMessage).toHaveBeenCalledWith('a-1', 'واتساب 07701234567')
    expect(await within(thread).findByText(/لا يُسمح بوضع معلومات اتصال|Direct contact details are not allowed/i)).toBeInTheDocument()
  })

  it('responds to an invitation without auto-applying', async () => {
    vi.mocked(jobsApi.listMyApplications).mockResolvedValue(paginated([]))
    vi.mocked(jobsApi.listMyInvitations).mockResolvedValue(
      paginated([{ id: 'inv-1', job: makeJobCard(), message: 'ندعوك للتقديم', status: 'PENDING', expires_at: '2026-10-01T00:00:00Z', created_at: '2026-09-22T00:00:00Z' }]),
    )
    vi.mocked(jobsApi.respondToInvitation).mockResolvedValue({ id: 'inv-1', job: makeJobCard(), message: '', status: 'ACCEPTED', expires_at: '2026-10-01T00:00:00Z', created_at: '2026-09-22T00:00:00Z' })
    renderApp('/jobs/my-applications')
    const row = await screen.findByTestId('invitation-row')
    const user = userEvent.setup()
    await user.click(within(row).getByRole('button', { name: /قبول الدعوة|Accept invitation/i }))
    expect(jobsApi.respondToInvitation).toHaveBeenCalledWith('inv-1', true)
    expect(jobsApi.applyToJob).not.toHaveBeenCalled()
    expect(await screen.findByText(/قبلتَ الدعوة|You accepted the invitation/i)).toBeInTheDocument()
  })

  describe('pagination', () => {
    const pageOf = (n: number) =>
      paginated(
        Array.from({ length: n === 3 ? 2 : 20 }, (_, i) => makeApplicationSeeker({ id: `a-${n}-${i}`, job: makeJobCard({ id: `j-${n}-${i}`, title: `Job ${n}-${i}` }) })),
        42,
      )

    it('reads the page from the URL, calls the API with it and renders the count', async () => {
      vi.mocked(jobsApi.listMyApplications).mockImplementation((page = 1) => Promise.resolve({ ...pageOf(page), next: page < 3 ? 'n' : null, previous: page > 1 ? 'p' : null }))
      renderApp('/jobs/my-applications?page=2')
      expect(await screen.findByText('Job 2-0')).toBeInTheDocument()
      expect(jobsApi.listMyApplications).toHaveBeenCalledWith(2, expect.anything())
      expect(screen.getByTestId('applications-count')).toHaveTextContent(/42/)
      expect(screen.getByText(/صفحة 2 من 3|Page 2 of 3/)).toBeInTheDocument()
    })

    it('moves with next and previous, showing the loading state while a page loads', async () => {
      const second = deferred<ReturnType<typeof pageOf>>()
      vi.mocked(jobsApi.listMyApplications).mockImplementation((page = 1) => {
        if (page === 2) return second.promise
        return Promise.resolve({ ...pageOf(page), next: page < 3 ? 'n' : null, previous: page > 1 ? 'p' : null })
      })
      const { router } = renderApp('/jobs/my-applications')
      expect(await screen.findByText('Job 1-0')).toBeInTheDocument()
      const user = userEvent.setup()
      await user.click(screen.getByRole('button', { name: /التالي|Next/i }))
      await waitFor(() => expect(router.state.location.search).toBe('?page=2'))
      expect(screen.getAllByTestId('async-loading').length).toBeGreaterThan(0)
      expect(screen.queryByText('Job 1-0')).toBeNull()
      second.resolve({ ...pageOf(2), next: 'n', previous: 'p' })
      expect(await screen.findByText('Job 2-0')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: /السابق|Previous/i }))
      await waitFor(() => expect(router.state.location.search).toBe(''))
      expect(await screen.findByText('Job 1-0')).toBeInTheDocument()
      expect(jobsApi.listMyApplications).toHaveBeenLastCalledWith(1, expect.anything())
    })

    it('keeps withdrawal working on a later page', async () => {
      vi.mocked(jobsApi.listMyApplications).mockImplementation((page = 1) => Promise.resolve({ ...pageOf(page), next: null, previous: page > 1 ? 'p' : null }))
      vi.mocked(jobsApi.withdrawApplication).mockResolvedValue(makeApplicationSeeker({ status: 'WITHDRAWN' }))
      renderApp('/jobs/my-applications?page=2')
      const cards = await screen.findAllByTestId('application-card')
      const user = userEvent.setup()
      const first = cards[0]
      if (!first) throw new Error('no card')
      await user.click(within(first).getByRole('button', { name: /سحب الطلب|Withdraw/i }))
      expect(jobsApi.withdrawApplication).toHaveBeenCalledWith('a-2-0')
      await waitFor(() => expect(jobsApi.listMyApplications).toHaveBeenLastCalledWith(2, expect.anything()))
    })

    it('shows an empty final page with a way back instead of the onboarding empty state', async () => {
      vi.mocked(jobsApi.listMyApplications).mockResolvedValue({ count: 40, next: null, previous: 'p', results: [] })
      renderApp('/jobs/my-applications?page=3')
      const empty = await screen.findByTestId('applications-empty-page')
      expect(within(empty).getByRole('link')).toHaveAttribute('href', '/jobs/my-applications')
      expect(screen.queryByTestId('applications-empty')).toBeNull()
    })
  })
})
