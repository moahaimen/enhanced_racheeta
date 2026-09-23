import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as jobsApi from '../../api/endpoints/jobs'
import { tokenStore } from '../../api/tokens'
import { makeApplicationSeeker, makeJobCard, paginated } from '../../test/jobFixtures'
import { makeAccount, renderApp } from '../../test/renderApp'

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
})
