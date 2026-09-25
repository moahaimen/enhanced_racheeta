import { screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as jobsApi from '../../api/endpoints/jobs'
import { tokenStore } from '../../api/tokens'
import { makeApplicationEmployer, makeEmployerOwner, makeJobEmployer, paginated } from '../../test/jobFixtures'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/jobs')

const VIEWER_NOTE = /دورك في المؤسسة|Your role in this organisation/

describe('ApplicantsPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'MEDICAL_COMPANY' }))
    vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(makeJobEmployer())
    vi.mocked(jobsApi.listJobApplications).mockResolvedValue(paginated([makeApplicationEmployer({ status: 'SHORTLISTED' })]))
    vi.mocked(jobsApi.listMessages).mockResolvedValue([])
  })

  it.each(['OWNER', 'RECRUITER'] as const)('shows %s the recruiter actions and the message composer', async (role) => {
    vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ my_role: role }))
    renderApp('/employer/jobs/j-1/applications')
    const card = await screen.findByTestId('applicant-card')
    expect(within(card).getByRole('button', { name: /طلب مقابلة|Request interview/ })).toBeInTheDocument()
    expect(within(card).getByRole('button', { name: /^قبول$|^Accept$/ })).toBeInTheDocument()
    expect(within(card).getByRole('button', { name: /^رفض$|^Reject$/ })).toBeInTheDocument()
    expect(within(card).getByLabelText(/السبب|Reason/)).toBeInTheDocument()
    expect(within(card).getByTestId('messages-thread')).toBeInTheDocument()
    expect(within(card).getByRole('link', { name: /ممرضة|Nurse/i })).toHaveAttribute('href', expect.stringContaining('/employer/talent/'))
    expect(screen.queryByText(VIEWER_NOTE)).toBeNull()
  })

  it.each([{ role: 'VIEWER' }, { role: undefined }])('hides every mutation control from role $role but keeps the applicant data', async ({ role }) => {
    const employer = makeEmployerOwner({ my_role: role as 'VIEWER' })
    if (role === undefined) delete (employer as Partial<typeof employer>).my_role
    vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(employer)
    renderApp('/employer/jobs/j-1/applications')
    const card = await screen.findByTestId('applicant-card')
    expect(screen.getByText(VIEWER_NOTE)).toBeInTheDocument()
    // read-only information stays: cover text, snapshot, skills, history, status badge, profile link
    expect(within(card).getByText('أرغب بالانضمام.')).toBeInTheDocument()
    expect(within(card).getByText('خبرة في العناية المركزة.')).toBeInTheDocument()
    expect(within(card).getByText('ICU')).toBeInTheDocument()
    // the candidate title is plain text: talent detail is a recruiter-only page
    expect(within(card).queryByRole('link', { name: /ممرضة|Nurse/i })).toBeNull()
    expect(within(card).getByText(/ممرضة|Nurse/i)).toBeInTheDocument()
    // no transition, interview, reason field or messaging
    expect(within(card).queryAllByRole('button')).toHaveLength(0)
    expect(within(card).queryByLabelText(/السبب|Reason/)).toBeNull()
    expect(within(card).queryByTestId('messages-thread')).toBeNull()
    expect(jobsApi.listMessages).not.toHaveBeenCalled()
    expect(jobsApi.transitionApplication).not.toHaveBeenCalled()
    // the status filter (a read control) is still there
    expect(screen.getByLabelText(/الحالة|Status/)).toBeInTheDocument()
  })

  it('keeps the loading and error states', async () => {
    vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner())
    const pending = deferred<ReturnType<typeof paginated<ReturnType<typeof makeApplicationEmployer>>>>()
    void pending.promise.catch(() => undefined) // the page handles the rejection; keep the test runner quiet
    vi.mocked(jobsApi.listJobApplications).mockReturnValue(pending.promise)
    renderApp('/employer/jobs/j-1/applications')
    expect(screen.queryByTestId('applicant-card')).toBeNull()
    pending.reject(new ApiError(500, 'server_error', 'boom'))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByTestId('applicant-card')).toBeNull()
  })
})
