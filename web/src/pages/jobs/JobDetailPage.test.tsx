import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as jobsApi from '../../api/endpoints/jobs'
import { tokenStore } from '../../api/tokens'
import { makeApplicationSeeker, makeJobPublic, makeSeekerProfile } from '../../test/jobFixtures'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/jobs')
vi.mock('../../api/endpoints/reference')

function signIn(overrides = {}) {
  tokenStore.set({ access: 'a', refresh: 'r' })
  vi.mocked(authApi.getMe).mockResolvedValue(makeAccount(overrides))
}

describe('JobDetailPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
    vi.mocked(jobsApi.getJob).mockResolvedValue(makeJobPublic())
  })

  it('shows the job, hides salary when not visible, and asks anonymous visitors to sign in', async () => {
    renderApp('/jobs/j-1')
    expect(await screen.findByRole('heading', { level: 1, name: 'ممرض قسم الطوارئ' })).toBeInTheDocument()
    expect(screen.getByText(/لم تُعلن جهة التوظيف الراتب|has not published the salary/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /سجّل الدخول للتقديم|Log in to apply/i })).toHaveAttribute('href', '/login')
    expect(screen.getByRole('link', { name: 'مستشفى الأمل' })).toHaveAttribute('href', '/employers/e-1')
  })

  it('shows a 404 state for an unknown job', async () => {
    vi.mocked(jobsApi.getJob).mockRejectedValue(new ApiError(404, 'not_found', 'missing'))
    renderApp('/jobs/nope')
    expect(await screen.findByText(/الوظيفة غير موجودة|not found|no longer available/i)).toBeInTheDocument()
  })

  it('points a signed-in user without a résumé to the profile page', async () => {
    signIn()
    vi.mocked(jobsApi.getMySeekerProfile).mockRejectedValue(new ApiError(404, 'not_found', 'none'))
    renderApp('/jobs/j-1')
    expect(await screen.findByRole('link', { name: /أكمل سيرتك المهنية|Complete your résumé/i })).toHaveAttribute('href', '/jobs/profile')
  })

  it('applies with the circular loading contract and shows the success state', async () => {
    signIn()
    vi.mocked(jobsApi.getMySeekerProfile).mockResolvedValue(makeSeekerProfile())
    const pending = deferred<ReturnType<typeof makeApplicationSeeker>>()
    vi.mocked(jobsApi.applyToJob).mockReturnValue(pending.promise)
    renderApp('/jobs/j-1')
    const user = userEvent.setup()
    const button = await screen.findByRole('button', { name: /قدّم على هذه الوظيفة|Apply for this job/i })
    await user.type(screen.getByLabelText(/رسالة تعريفية|Cover message/i), 'أرغب بالانضمام')
    await user.click(button)
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    await user.click(button) // duplicate click ignored while pending
    expect(jobsApi.applyToJob).toHaveBeenCalledTimes(1)
    expect(jobsApi.applyToJob).toHaveBeenCalledWith('j-1', 'أرغب بالانضمام')
    pending.resolve(makeApplicationSeeker())
    expect(await screen.findByText(/تم إرسال طلبك|Your application was sent/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /طلباتي|My applications/i })).toHaveAttribute('href', '/jobs/my-applications')
  })

  it('renders the localized contact-blocking error on the cover text field', async () => {
    signIn()
    vi.mocked(jobsApi.getMySeekerProfile).mockResolvedValue(makeSeekerProfile())
    vi.mocked(jobsApi.applyToJob).mockRejectedValue(
      new ApiError(400, 'validation_error', 'Validation failed.', { cover_text: ['Contact information is not allowed.'] }, { cover_text: ['contact_information_not_allowed'] }),
    )
    renderApp('/jobs/j-1')
    const user = userEvent.setup()
    const button = await screen.findByRole('button', { name: /قدّم على هذه الوظيفة|Apply for this job/i })
    await user.type(screen.getByLabelText(/رسالة تعريفية|Cover message/i), 'اتصل بي 07701234567')
    await user.click(button)
    expect(await screen.findByText(/لا يُسمح بوضع معلومات اتصال|Direct contact details are not allowed/i)).toBeInTheDocument()
    await waitFor(() => expect(button).toBeEnabled())
  })

  it('renders the localized usage-limit error as a form error', async () => {
    signIn()
    vi.mocked(jobsApi.getMySeekerProfile).mockResolvedValue(makeSeekerProfile())
    vi.mocked(jobsApi.applyToJob).mockRejectedValue(new ApiError(402, 'usage_limit_reached', 'limit', undefined, undefined, { key: 'applications.limit', limit: 15, used: 15 }))
    renderApp('/jobs/j-1')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /قدّم على هذه الوظيفة|Apply for this job/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/وصلت إلى حد خطتك|reached the limit/i)
  })

  it('does not offer the apply form on a closed job', async () => {
    vi.mocked(jobsApi.getJob).mockResolvedValue(makeJobPublic({ is_open: false }))
    signIn()
    vi.mocked(jobsApi.getMySeekerProfile).mockResolvedValue(makeSeekerProfile())
    renderApp('/jobs/j-1')
    expect(await screen.findByText(/غير مفتوحة للتقديم|not open for applications/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /قدّم على هذه الوظيفة|Apply for this job/i })).toBeNull()
  })
})
