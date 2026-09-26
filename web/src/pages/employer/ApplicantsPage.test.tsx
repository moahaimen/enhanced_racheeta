import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as jobsApi from '../../api/endpoints/jobs'
import { tokenStore } from '../../api/tokens'
import { makeApplicationEmployer, makeBilling, makeEmployerOwner, makeJobEmployer, paginated } from '../../test/jobFixtures'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/jobs')

const VIEWER_NOTE = /دورك في المؤسسة|Your role in this organisation/
const SEND = /^إرسال$|^Send$/i

function billingWith(keys: string[]) {
  return makeBilling({
    entitlements: keys.map((key) => ({ key, kind: 'BOOLEAN' as const, enabled: true, limit: null, period: 'NONE' as const, used: 0, credits: 0, remaining: null })),
  })
}

describe('ApplicantsPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'MEDICAL_COMPANY' }))
    vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(makeJobEmployer())
    vi.mocked(jobsApi.listJobApplications).mockResolvedValue(paginated([makeApplicationEmployer({ status: 'SHORTLISTED' })]))
    vi.mocked(jobsApi.listMessages).mockResolvedValue([])
    vi.mocked(jobsApi.getEmployerBilling).mockResolvedValue(billingWith(['jobs.application_review', 'recruitment.messaging', 'talent.search']))
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

  describe('messaging follows recruitment.messaging', () => {
    it('shows the composer and sends when both capabilities are present', async () => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ my_role: 'RECRUITER' }))
      vi.mocked(jobsApi.sendMessage).mockResolvedValue({ id: 'm-1', sender_side: 'EMPLOYER', body: 'Hello', created_at: '2026-09-25T00:00:00Z' })
      renderApp('/employer/jobs/j-1/applications')
      const card = await screen.findByTestId('applicant-card')
      const user = userEvent.setup()
      await user.type(within(card).getByRole('textbox', { name: /الرسائل|Messages/i }), 'Hello')
      await user.click(within(card).getByRole('button', { name: SEND }))
      await waitFor(() => expect(jobsApi.sendMessage).toHaveBeenCalledWith('a-1', 'Hello'))
    })

    it.each([
      ['messaging disabled', () => billingWith(['jobs.application_review'])],
      ['messaging row missing', () => makeBilling({ entitlements: [] })],
    ])('keeps the history but hides the composer (%s)', async (_label, billing) => {
      vi.mocked(jobsApi.getEmployerBilling).mockResolvedValue(billing())
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner())
      renderApp('/employer/jobs/j-1/applications')
      const card = await screen.findByTestId('applicant-card')
      if (_label === 'messaging disabled') {
        expect(within(card).getByTestId('messages-thread')).toBeInTheDocument() // read history
        expect(within(card).getByRole('button', { name: /^قبول$|^Accept$/ })).toBeInTheDocument()
      } else {
        expect(within(card).queryByTestId('messages-thread')).toBeNull() // no application_review either
      }
      expect(within(card).queryByRole('button', { name: SEND })).toBeNull()
      expect(within(card).queryByRole('textbox', { name: /الرسائل|Messages/i })).toBeNull()
      expect(within(card).getByText('أرغب بالانضمام.')).toBeInTheDocument()
    })

    it('exposes no composer while the billing summary is still loading', async () => {
      vi.mocked(jobsApi.getEmployerBilling).mockReturnValue(new Promise(() => undefined))
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner())
      renderApp('/employer/jobs/j-1/applications')
      await waitFor(() => expect(jobsApi.getEmployerBilling).toHaveBeenCalled())
      expect(screen.queryByRole('button', { name: SEND })).toBeNull()
      expect(screen.queryByTestId('applicant-card')).toBeNull()
    })

    it('never shows the composer to a VIEWER even when the plan allows messaging', async () => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ my_role: 'VIEWER' }))
      renderApp('/employer/jobs/j-1/applications')
      const card = await screen.findByTestId('applicant-card')
      expect(within(card).queryByRole('button', { name: SEND })).toBeNull()
      expect(within(card).queryByTestId('messages-thread')).toBeNull()
    })
  })

  describe('talent link follows talent.search', () => {
    const NAME = /ممرضة|Nurse/i

    it.each(['OWNER', 'RECRUITER'] as const)('links the applicant for a %s whose plan includes talent search', async (role) => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ my_role: role }))
      renderApp('/employer/jobs/j-1/applications')
      const card = await screen.findByTestId('applicant-card')
      expect(within(card).getByRole('link', { name: NAME })).toHaveAttribute('href', expect.stringContaining('/employer/talent/'))
    })

    it.each([
      ['talent.search=false (TRIAL-shaped)', () => billingWith(['jobs.application_review', 'recruitment.messaging'])],
      ['talent.search row missing', () => makeBilling({ entitlements: [{ key: 'jobs.application_review', kind: 'BOOLEAN', enabled: true, limit: null, period: 'NONE', used: 0, credits: 0, remaining: null }] })],
    ])('keeps the applicant visible and reviewable but unlinked (%s)', async (_label, billing) => {
      vi.mocked(jobsApi.getEmployerBilling).mockResolvedValue(billing())
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner())
      renderApp('/employer/jobs/j-1/applications')
      const card = await screen.findByTestId('applicant-card')
      expect(within(card).queryByRole('link', { name: NAME })).toBeNull()
      expect(within(card).getByText(NAME)).toBeInTheDocument()
      expect(within(card).getByRole('button', { name: /^قبول$|^Accept$/ })).toBeInTheDocument() // review still works
    })

    it('does not link for a VIEWER even with the entitlement', async () => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ my_role: 'VIEWER' }))
      renderApp('/employer/jobs/j-1/applications')
      const card = await screen.findByTestId('applicant-card')
      expect(within(card).queryByRole('link', { name: NAME })).toBeNull()
    })
  })
})
