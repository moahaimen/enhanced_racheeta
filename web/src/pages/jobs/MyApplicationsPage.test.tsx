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
    const pendingInvite = { id: 'inv-1', job: makeJobCard(), message: 'ندعوك للتقديم', status: 'PENDING' as const, expires_at: '2026-10-01T00:00:00Z', created_at: '2026-09-22T00:00:00Z' }
    vi.mocked(jobsApi.listMyInvitations)
      .mockResolvedValueOnce(paginated([pendingInvite]))
      .mockResolvedValue(paginated([{ ...pendingInvite, status: 'ACCEPTED' as const }]))
    vi.mocked(jobsApi.respondToInvitation).mockResolvedValue({ id: 'inv-1', job: makeJobCard(), message: '', status: 'ACCEPTED', expires_at: '2026-10-01T00:00:00Z', created_at: '2026-09-22T00:00:00Z' })
    renderApp('/jobs/my-applications')
    const row = await screen.findByTestId('invitation-row')
    const user = userEvent.setup()
    await user.click(within(row).getByRole('button', { name: /قبول الدعوة|Accept invitation/i }))
    expect(jobsApi.respondToInvitation).toHaveBeenCalledWith('inv-1', true)
    expect(jobsApi.applyToJob).not.toHaveBeenCalled()
    expect(await screen.findByTestId('invitation-accepted-hint')).toHaveTextContent(/قبلتَ الدعوة|You accepted the invitation/i)
    expect(within(await screen.findByTestId('invitation-row')).queryByRole('button', { name: /قبول الدعوة|Accept invitation/i })).toBeNull()
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

  describe('invitations pagination', () => {
    const invitesPage = (n: number, size = 20) =>
      paginated(
        Array.from({ length: size }, (_, i) => ({ id: `inv-${n}-${i}`, job: makeJobCard({ id: `j-${n}-${i}`, title: `Invite job ${n}-${i}` }), message: '', status: 'PENDING' as const, expires_at: '2026-10-01T00:00:00Z', created_at: '2026-09-22T00:00:00Z' })),
        25,
      )
    const answered = (id: string, status: 'ACCEPTED' | 'DECLINED') => ({ id, job: makeJobCard(), message: '', status, expires_at: '2026-10-01T00:00:00Z', created_at: '2026-09-22T00:00:00Z' })

    beforeEach(() => {
      vi.mocked(jobsApi.listMyApplications).mockResolvedValue(paginated([]))
    })

    it('reads ?invites_page= independently of ?page= and shows the loading state while paging', async () => {
      const second = deferred<ReturnType<typeof invitesPage>>()
      vi.mocked(jobsApi.listMyInvitations).mockImplementation((page = 1) => {
        if (page === 2) return second.promise
        return Promise.resolve({ ...invitesPage(1), next: 'n', previous: null })
      })
      const { router } = renderApp('/jobs/my-applications')
      expect(await screen.findByText('Invite job 1-0')).toBeInTheDocument()
      expect(screen.getAllByTestId('invitation-row')).toHaveLength(20)
      const user = userEvent.setup()
      await user.click(screen.getByRole('button', { name: /التالي|Next/i }))
      await waitFor(() => expect(router.state.location.search).toBe('?invites_page=2'))
      expect(await screen.findByTestId('invitations-loading')).toBeInTheDocument()
      second.resolve({ ...invitesPage(2, 5), next: null, previous: 'p' })
      expect(await screen.findByText('Invite job 2-0')).toBeInTheDocument()
      expect(jobsApi.listMyInvitations).toHaveBeenLastCalledWith(2, expect.anything())
      expect(jobsApi.listMyApplications).toHaveBeenLastCalledWith(1, expect.anything()) // applications page untouched
      await user.click(screen.getByRole('button', { name: /السابق|Previous/i }))
      await waitFor(() => expect(router.state.location.search).toBe(''))
      expect(await screen.findByText('Invite job 1-0')).toBeInTheDocument()
    })

    it('accepts and declines invitations on page 2', async () => {
      vi.mocked(jobsApi.listMyInvitations).mockImplementation((page = 1) => Promise.resolve({ ...invitesPage(page, page === 2 ? 5 : 20), next: page < 2 ? 'n' : null, previous: page > 1 ? 'p' : null }))
      vi.mocked(jobsApi.respondToInvitation).mockImplementation((id, accept) => Promise.resolve(answered(id, accept ? 'ACCEPTED' : 'DECLINED')))
      renderApp('/jobs/my-applications?invites_page=2')
      const rows = await screen.findAllByTestId('invitation-row')
      expect(rows).toHaveLength(5)
      const user = userEvent.setup()
      const first = rows[0]
      const second = rows[1]
      if (!first || !second) throw new Error('rows missing')
      await user.click(within(first).getByRole('button', { name: /قبول الدعوة|Accept invitation/i }))
      expect(jobsApi.respondToInvitation).toHaveBeenCalledWith('inv-2-0', true)
      await waitFor(() => expect(jobsApi.listMyInvitations).toHaveBeenLastCalledWith(2, expect.anything()))
      const again = await screen.findAllByTestId('invitation-row')
      const target = again[1]
      if (!target) throw new Error('row missing')
      await user.click(within(target).getByRole('button', { name: /رفض الدعوة|Decline invitation/i }))
      expect(jobsApi.respondToInvitation).toHaveBeenCalledWith('inv-2-1', false)
    })

    it('shows an empty final invitations page with a way back', async () => {
      vi.mocked(jobsApi.listMyInvitations).mockResolvedValue({ count: 20, next: null, previous: 'p', results: [] })
      renderApp('/jobs/my-applications?invites_page=3')
      expect(await screen.findByTestId('invitations-empty-page')).toBeInTheDocument()
    })
  })

  describe('review round four', () => {
    const interview = (status: 'PROPOSED' | 'ACCEPTED' | 'DECLINED' | 'CANCELLED') => ({ id: 'iv-1', proposed_at: '2026-10-01T10:00:00Z', mode: 'IN_PERSON' as const, location_text: '', employer_note: '', status, candidate_response: '', responded_at: null, created_at: '2026-09-22T00:00:00Z' })
    const invite = (id: string, status: 'PENDING' | 'ACCEPTED' | 'DECLINED' | 'EXPIRED' | 'CANCELLED') => ({ id, job: makeJobCard({ id: `job-${id}`, title: `Job ${id}` }), message: '', status, expires_at: '2026-10-01T00:00:00Z', created_at: '2026-09-22T00:00:00Z' })

    it('lets the seeker withdraw while the application is in INTERVIEW, with the loading contract', async () => {
      vi.mocked(jobsApi.listMyApplications).mockResolvedValue(paginated([makeApplicationSeeker({ status: 'INTERVIEW', interviews: [interview('PROPOSED')] })]))
      const pending = deferred<ReturnType<typeof makeApplicationSeeker>>()
      vi.mocked(jobsApi.withdrawApplication).mockReturnValue(pending.promise)
      renderApp('/jobs/my-applications')
      const card = await screen.findByTestId('application-card')
      const withdraw = within(card).getByRole('button', { name: /سحب الطلب|Withdraw/i })
      const user = userEvent.setup()
      await user.click(withdraw)
      expect(withdraw).toBeDisabled()
      expect(withdraw).toHaveAttribute('aria-busy', 'true')
      await user.click(withdraw)
      expect(jobsApi.withdrawApplication).toHaveBeenCalledTimes(1)
      pending.resolve(makeApplicationSeeker({ status: 'WITHDRAWN' }))
      await waitFor(() => expect(jobsApi.listMyApplications).toHaveBeenCalledTimes(2))
    })

    it.each(['ACCEPTED', 'REJECTED', 'WITHDRAWN'] as const)('offers no withdrawal and no interview answers once the application is %s', async (status) => {
      vi.mocked(jobsApi.listMyApplications).mockResolvedValue(paginated([makeApplicationSeeker({ status, interviews: [interview('PROPOSED')] })]))
      renderApp('/jobs/my-applications')
      const card = await screen.findByTestId('application-card')
      expect(within(card).queryByRole('button', { name: /سحب الطلب|Withdraw/i })).toBeNull()
      expect(within(card).queryByRole('button', { name: /قبول الموعد|Accept the time/i })).toBeNull()
      expect(within(card).queryByRole('button', { name: /اعتذار|Decline/i })).toBeNull()
    })

    it('shows interview answers while the application is open', async () => {
      vi.mocked(jobsApi.listMyApplications).mockResolvedValue(paginated([makeApplicationSeeker({ status: 'INTERVIEW', interviews: [interview('PROPOSED')] })]))
      renderApp('/jobs/my-applications')
      const card = await screen.findByTestId('application-card')
      expect(within(card).getByRole('button', { name: /قبول الموعد|Accept the time/i })).toBeInTheDocument()
    })

    it('shows the acceptance guidance only for ACCEPTED invitations', async () => {
      vi.mocked(jobsApi.listMyApplications).mockResolvedValue(paginated([]))
      vi.mocked(jobsApi.listMyInvitations).mockResolvedValue(paginated([invite('p', 'PENDING'), invite('a', 'ACCEPTED'), invite('d', 'DECLINED'), invite('e', 'EXPIRED'), invite('c', 'CANCELLED')]))
      renderApp('/jobs/my-applications')
      const rows = await screen.findAllByTestId('invitation-row')
      expect(rows).toHaveLength(5)
      const [pendingRow, acceptedRow, declinedRow, expiredRow, cancelledRow] = rows
      if (!pendingRow || !acceptedRow || !declinedRow || !expiredRow || !cancelledRow) throw new Error('rows missing')
      expect(within(pendingRow).getByRole('button', { name: /قبول الدعوة|Accept invitation/i })).toBeInTheDocument()
      expect(within(pendingRow).getByRole('button', { name: /رفض الدعوة|Decline invitation/i })).toBeInTheDocument()
      expect(within(pendingRow).queryByTestId('invitation-accepted-hint')).toBeNull()
      expect(within(acceptedRow).getByTestId('invitation-accepted-hint')).toHaveTextContent(/قبلتَ الدعوة|You accepted the invitation/)
      expect(within(acceptedRow).queryByRole('button')).toBeNull()
      for (const row of [declinedRow, expiredRow, cancelledRow]) {
        expect(within(row).queryByTestId('invitation-accepted-hint')).toBeNull()
        expect(within(row).queryByRole('button')).toBeNull()
      }
      expect(screen.getAllByTestId('invitation-accepted-hint')).toHaveLength(1)
    })
  })
})
