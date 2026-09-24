import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as jobsApi from '../../api/endpoints/jobs'
import * as referenceApi from '../../api/endpoints/reference'
import { tokenStore } from '../../api/tokens'
import { makeBilling, makeEmployerOwner, makeJobEmployer, makePlan, paginated } from '../../test/jobFixtures'
import { baghdad } from '../../test/providerFixtures'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/jobs')
vi.mock('../../api/endpoints/providers')
vi.mock('../../api/endpoints/reference')

describe('EmployerWorkspacePage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'MEDICAL_COMPANY' }))
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad])
    vi.mocked(referenceApi.listCities).mockResolvedValue([])
    vi.mocked(jobsApi.getEmployerBilling).mockResolvedValue(makeBilling())
    vi.mocked(jobsApi.listEmployerJobs).mockResolvedValue(paginated([]))
    vi.mocked(jobsApi.listMembers).mockResolvedValue([])
  })

  it('onboards an account without an organisation', async () => {
    vi.mocked(jobsApi.getMyEmployer).mockRejectedValueOnce(new ApiError(404, 'not_found', 'none')).mockResolvedValue(makeEmployerOwner({ verification_status: 'UNVERIFIED', is_verified: false }))
    vi.mocked(jobsApi.createMyEmployer).mockResolvedValue(makeEmployerOwner({ verification_status: 'UNVERIFIED', is_verified: false }))
    renderApp('/employer')
    expect(await screen.findByRole('heading', { level: 1, name: /سجّل مؤسستك|Register your organisation/i })).toBeInTheDocument()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/اسم المؤسسة|Organisation name/i), 'مستشفى الأمل')
    await user.selectOptions(screen.getByLabelText(/المحافظة$|^Governorate/i), 'g-baghdad')
    await user.click(screen.getByRole('button', { name: /تسجيل المؤسسة|Register organisation/i }))
    await waitFor(() => expect(jobsApi.createMyEmployer).toHaveBeenCalledWith(expect.objectContaining({ name: 'مستشفى الأمل', governorate: 'g-baghdad', organization_type: 'HOSPITAL' })))
    expect(await screen.findByRole('heading', { level: 1, name: 'مستشفى الأمل' })).toBeInTheDocument()
  })

  it('lets an unverified owner request verification', async () => {
    vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ verification_status: 'UNVERIFIED', is_verified: false }))
    vi.mocked(jobsApi.requestEmployerVerification).mockResolvedValue(makeEmployerOwner({ verification_status: 'PENDING', is_verified: false }))
    renderApp('/employer')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /طلب التوثيق|Request verification/i }))
    expect(jobsApi.requestEmployerVerification).toHaveBeenCalledTimes(1)
    expect((await screen.findAllByText(/قيد المراجعة|Pending review/i)).length).toBeGreaterThan(0)
    // Talent search is not offered before verification.
    expect(screen.queryByRole('link', { name: /البحث عن الكوادر|Talent search/i })).toBeNull()
  })

  it('shows jobs, usage meters and lets the owner request a plan', async () => {
    vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner())
    vi.mocked(jobsApi.listEmployerJobs).mockResolvedValue(paginated([makeJobEmployer({ status: 'PUBLISHED', applications_count: 3 })]))
    vi.mocked(jobsApi.requestPlan).mockResolvedValue({ id: 'sub-1', plan: makePlan({ code: 'PROFESSIONAL' }), status: 'PENDING', requester_note: '', starts_at: null, ends_at: null, created_at: '2026-09-22T00:00:00Z' })
    renderApp('/employer')
    const row = await screen.findByTestId('employer-job-row')
    expect(within(row).getByRole('link', { name: 'ممرض قسم الطوارئ' })).toHaveAttribute('href', '/employer/jobs/j-1')
    expect(within(row).getByText(/منشورة|Published/)).toBeInTheDocument()
    const meters = await screen.findByTestId('usage-meters')
    expect(within(meters).getByText(/الوظائف النشطة|Active jobs/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /البحث عن الكوادر|Talent search/i })).toHaveAttribute('href', '/employer/talent')

    const user = userEvent.setup()
    const submit = screen.getByRole('button', { name: /إرسال طلب الاشتراك|Send subscription request/i })
    await user.click(submit)
    expect(jobsApi.requestPlan).not.toHaveBeenCalled()
    await user.click(screen.getByRole('radio', { name: /احترافية|Professional/i }))
    await user.click(submit)
    await waitFor(() => expect(jobsApi.requestPlan).toHaveBeenCalledWith('PROFESSIONAL', ''))
    expect(await screen.findByText(/أُرسل طلبك|Your request was sent/i)).toBeInTheDocument()
    // Prices are never invented on the client: the plan card says "on request" when the API has none.
    expect(screen.queryByText(/IQD\s*\d/)).toBeNull()
  })

  describe('jobs pagination', () => {
    const jobsPage = (page: number) =>
      paginated(
        Array.from({ length: 20 }, (_, i) => makeJobEmployer({ id: `j-${page}-${i}`, title: `Job ${page}-${i}`, status: 'CLOSED' })),
        35,
      )

    it('uses the server active-job count, not the visible page', async () => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ active_jobs: 7 }))
      vi.mocked(jobsApi.listEmployerJobs).mockResolvedValue({ ...jobsPage(1), next: 'n', previous: null })
      renderApp('/employer')
      expect(await screen.findByTestId('active-jobs-stat')).toHaveTextContent('7')
      expect(await screen.findAllByTestId('employer-job-row')).toHaveLength(20)
    })

    it('navigates to page 2 through the URL with a loading indicator and the right API call', async () => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ active_jobs: 7 }))
      const second = deferred<ReturnType<typeof jobsPage>>()
      vi.mocked(jobsApi.listEmployerJobs).mockImplementation((_status, page = 1) => {
        if (page === 2) return second.promise
        return Promise.resolve({ ...jobsPage(1), next: 'n', previous: null })
      })
      const { router } = renderApp('/employer')
      expect(await screen.findByText('Job 1-0')).toBeInTheDocument()
      const user = userEvent.setup()
      await user.click(screen.getByRole('button', { name: /التالي|Next/i }))
      await waitFor(() => expect(router.state.location.search).toBe('?jobs_page=2'))
      expect(await screen.findByTestId('jobs-loading')).toBeInTheDocument()
      expect(screen.getByTestId('active-jobs-stat')).toHaveTextContent('7')
      second.resolve({ ...jobsPage(2), next: null, previous: 'p' })
      expect(await screen.findByText('Job 2-0')).toBeInTheDocument()
      expect(jobsApi.listEmployerJobs).toHaveBeenLastCalledWith('', 2, expect.anything())
    })
  })

  describe('identity lock after verification', () => {
    it('disables the identity fields for a verified organisation and only submits editable ones', async () => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ verification_status: 'VERIFIED' }))
      vi.mocked(jobsApi.updateMyEmployer).mockResolvedValue(makeEmployerOwner({ verification_status: 'VERIFIED', description: 'updated' }))
      renderApp('/employer')
      const nameField = await screen.findByLabelText(/اسم المؤسسة|Organisation name/i)
      expect(nameField).toBeDisabled()
      expect(screen.getByLabelText(/نوع المؤسسة|Organisation type/i)).toBeDisabled()
      expect(screen.getByLabelText(/مكتب توظيف|Recruitment agency/i)).toBeDisabled()
      expect(screen.getByText(/تُقفل بيانات هوية المؤسسة|identity fields .* are locked/i)).toBeInTheDocument()
      const user = userEvent.setup()
      const description = screen.getByLabelText(/نبذة عن المؤسسة|About the organisation/i)
      expect(description).toBeEnabled()
      await user.type(description, ' updated')
      await user.click(screen.getByRole('button', { name: /^حفظ$|^Save$/i }))
      await waitFor(() => expect(jobsApi.updateMyEmployer).toHaveBeenCalledTimes(1))
      const payload = vi.mocked(jobsApi.updateMyEmployer).mock.calls[0]?.[0]
      expect(payload).not.toHaveProperty('organization_type')
      expect(payload).not.toHaveProperty('name')
      expect(payload).toHaveProperty('description')
    })

    it('keeps the identity fields editable before verification is requested', async () => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ verification_status: 'UNVERIFIED', is_verified: false }))
      renderApp('/employer')
      expect(await screen.findByLabelText(/اسم المؤسسة|Organisation name/i)).toBeEnabled()
      expect(screen.getByLabelText(/نوع المؤسسة|Organisation type/i)).toBeEnabled()
    })
  })
})
