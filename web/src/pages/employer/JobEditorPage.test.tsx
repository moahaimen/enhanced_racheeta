import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as jobsApi from '../../api/endpoints/jobs'
import * as referenceApi from '../../api/endpoints/reference'
import { tokenStore } from '../../api/tokens'
import { makeBilling, makeEmployerOwner, makeEmployerPublic, makeJobEmployer } from '../../test/jobFixtures'
import { baghdad, cardiology } from '../../test/providerFixtures'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/jobs')
vi.mock('../../api/endpoints/reference')

/** A billing summary whose plan carries exactly the given boolean capabilities. */
function billingWith(keys: string[]) {
  return makeBilling({
    entitlements: keys.map((key) => ({ key, kind: 'BOOLEAN' as const, enabled: true, limit: null, period: 'NONE' as const, used: 0, credits: 0, remaining: null })),
  })
}

/** Seeded plans as the summary reports them: TRIAL and BASIC carry jobs.post but no jobs.featured. */
function seededPlan(code: 'TRIAL' | 'BASIC') {
  return makeBilling({
    entitlements: [
      { key: 'jobs.post', kind: 'BOOLEAN', enabled: true, limit: null, period: 'NONE', used: 0, credits: 0, remaining: null },
      { key: 'jobs.featured', kind: 'BOOLEAN', enabled: false, limit: null, period: 'NONE', used: 0, credits: 0, remaining: null },
      { key: 'jobs.application_review', kind: 'BOOLEAN', enabled: true, limit: null, period: 'NONE', used: 0, credits: 0, remaining: null },
      { key: 'jobs.active_limit', kind: 'LIMIT', enabled: true, limit: code === 'TRIAL' ? 1 : 3, period: 'NONE', used: 0, credits: 0, remaining: 1 },
    ],
  })
}

describe('JobEditorPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'MEDICAL_COMPANY' }))
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad])
    vi.mocked(referenceApi.listSpecialties).mockResolvedValue([cardiology])
    vi.mocked(referenceApi.listCities).mockResolvedValue([])
    vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner())
    vi.mocked(jobsApi.getEmployerBilling).mockResolvedValue(billingWith(['jobs.post', 'jobs.featured', 'jobs.application_review']))
  })

  it('creates a draft after client validation and moves to the job page', async () => {
    vi.mocked(jobsApi.createJob).mockResolvedValue(makeJobEmployer())
    vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(makeJobEmployer())
    const { router } = renderApp('/employer/jobs/new')
    const user = userEvent.setup()
    const create = await screen.findByRole('button', { name: /إنشاء المسودة|Create draft/i })
    await user.click(create)
    expect(jobsApi.createJob).not.toHaveBeenCalled()
    await user.type(screen.getByLabelText(/المسمى الوظيفي|Job title/i), 'ممرض قسم الطوارئ')
    await user.type(screen.getByLabelText(/وصف الوظيفة|Job description/i), 'العمل ضمن فريق الطوارئ.')
    await user.click(create)
    await waitFor(() => expect(jobsApi.createJob).toHaveBeenCalledWith(expect.objectContaining({ title: 'ممرض قسم الطوارئ', governorate: 'g-baghdad', profession: 'NURSE', salary_visible: false })))
    await waitFor(() => expect(router.state.location.pathname).toBe('/employer/jobs/j-1'))
  })

  it('submits a draft for review with the loading contract and shows the limit error', async () => {
    vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(makeJobEmployer())
    const pending = deferred<ReturnType<typeof makeJobEmployer>>()
    vi.mocked(jobsApi.jobAction).mockReturnValue(pending.promise)
    renderApp('/employer/jobs/j-1')
    const user = userEvent.setup()
    const submit = await screen.findByRole('button', { name: /إرسال للمراجعة|Submit for review/i })
    await user.click(submit)
    expect(submit).toBeDisabled()
    await user.click(submit)
    expect(jobsApi.jobAction).toHaveBeenCalledTimes(1)
    expect(jobsApi.jobAction).toHaveBeenCalledWith('j-1', 'submit')
    pending.reject(new ApiError(402, 'usage_limit_reached', 'limit', undefined, undefined, { key: 'jobs.active_limit', limit: 1, used: 1 }))
    expect(await screen.findByText(/وصلت إلى حد خطتك|reached your plan's limit/i)).toBeInTheDocument()
    await waitFor(() => expect(submit).toBeEnabled())
  })

  it('shows moderation flags and the rejection note on a rejected job', async () => {
    vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(
      makeJobEmployer({ status: 'REJECTED', moderation_note: 'يحتوي على رقم هاتف', moderation_flags: [{ field: 'description', category: 'PHONE', excerpt: '0770…' }] }),
    )
    renderApp('/employer/jobs/j-1')
    expect(await screen.findByText('يحتوي على رقم هاتف')).toBeInTheDocument()
    expect(screen.getByText(/PHONE/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /إرسال للمراجعة|Submit for review/i })).toBeInTheDocument()
  })

  describe('hiring fields retained by a former agency', () => {
    const retained = () =>
      makeJobEmployer({ hiring_employer: makeEmployerPublic({ id: 'e-2', name: 'مستشفى الكرادة' }), hiring_organization_name: 'عيادة الكرادة' })

    it('warns about the retained values and clears them on save so the draft is repairable', async () => {
      // The organisation is no longer an agency, so the editor cannot show the
      // two hiring fields — and the backend refuses every save while the
      // RESULTING job still carries them. The save must clear them explicitly.
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ is_recruitment_agency: false }))
      vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(retained())
      vi.mocked(jobsApi.updateJob).mockResolvedValue(makeJobEmployer())
      renderApp('/employer/jobs/j-1')
      expect(await screen.findByTestId('retained-hiring-notice')).toBeInTheDocument()
      const user = userEvent.setup()
      const save = screen.getByRole('button', { name: /حفظ المسودة|Save draft/i })
      await user.click(save)
      await waitFor(() => expect(jobsApi.updateJob).toHaveBeenCalledTimes(1))
      const [id, payload] = vi.mocked(jobsApi.updateJob).mock.calls[0]!
      expect(id).toBe('j-1')
      expect(payload.hiring_employer).toBeNull()
      expect(payload.hiring_organization_name).toBe('')
      // Nothing else is invented: the rest of the payload is the loaded job.
      expect(payload.title).toBe('ممرض قسم الطوارئ')
    })

    it('keeps the save button disabled while the repair is in flight', async () => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ is_recruitment_agency: false }))
      vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(retained())
      const pending = deferred<ReturnType<typeof makeJobEmployer>>()
      vi.mocked(jobsApi.updateJob).mockReturnValue(pending.promise)
      renderApp('/employer/jobs/j-1')
      const user = userEvent.setup()
      const save = await screen.findByRole('button', { name: /حفظ المسودة|Save draft/i })
      await user.click(save)
      expect(save).toBeDisabled()
      await user.click(save)
      expect(jobsApi.updateJob).toHaveBeenCalledTimes(1)
      pending.resolve(makeJobEmployer())
      await waitFor(() => expect(save).toBeEnabled())
    })

    it('shows no warning and sends no clearing values for a clean non-agency job', async () => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ is_recruitment_agency: false }))
      vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(makeJobEmployer())
      vi.mocked(jobsApi.updateJob).mockResolvedValue(makeJobEmployer())
      renderApp('/employer/jobs/j-1')
      await screen.findByRole('button', { name: /حفظ المسودة|Save draft/i })
      expect(screen.queryByTestId('retained-hiring-notice')).toBeNull()
    })

    it('never sends agency-only values when a non-agency creates a job', async () => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ is_recruitment_agency: false }))
      vi.mocked(jobsApi.createJob).mockResolvedValue(makeJobEmployer())
      vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(makeJobEmployer())
      renderApp('/employer/jobs/new')
      const user = userEvent.setup()
      await user.type(await screen.findByLabelText(/المسمى الوظيفي|Job title/i), 'ممرض')
      await user.type(screen.getByLabelText(/وصف الوظيفة|Job description/i), 'وصف.')
      await user.click(screen.getByRole('button', { name: /إنشاء المسودة|Create draft/i }))
      await waitFor(() => expect(jobsApi.createJob).toHaveBeenCalledTimes(1))
      const payload = vi.mocked(jobsApi.createJob).mock.calls[0]![0]
      expect(payload).not.toHaveProperty('hiring_employer')
      expect(payload).not.toHaveProperty('hiring_organization_name')
    })

    it('still lets a real agency edit both hiring fields', async () => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ is_recruitment_agency: true }))
      vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(retained())
      vi.mocked(jobsApi.updateJob).mockResolvedValue(retained())
      renderApp('/employer/jobs/j-1')
      expect(screen.queryByTestId('retained-hiring-notice')).toBeNull()
      const nameField = await screen.findByLabelText(/اسم المؤسسة الفعلية|actual organisation/i)
      expect(nameField).toHaveValue('عيادة الكرادة')
      const user = userEvent.setup()
      await user.clear(nameField)
      await user.type(nameField, 'عيادة المنصور')
      await user.click(screen.getByRole('button', { name: /حفظ المسودة|Save draft/i }))
      await waitFor(() => expect(jobsApi.updateJob).toHaveBeenCalledTimes(1))
      const payload = vi.mocked(jobsApi.updateJob).mock.calls[0]![1]
      expect(payload.hiring_organization_name).toBe('عيادة المنصور')
      expect(payload.hiring_employer).toBe('e-2')
    })
  })

  it('locks the form for a published job and offers close', async () => {
    vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(makeJobEmployer({ status: 'PUBLISHED' }))
    renderApp('/employer/jobs/j-1')
    expect(await screen.findByRole('button', { name: /إغلاق الوظيفة|Close job/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^حفظ$|^Save$/i })).toBeNull()
    expect(screen.getByLabelText(/المسمى الوظيفي|Job title/i)).toBeDisabled()
  })

  it('shows a VIEWER a read-only editor when reached directly by URL', async () => {
    vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ my_role: 'VIEWER' }))
    vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(makeJobEmployer())
    renderApp('/employer/jobs/j-1')
    expect(await screen.findByText(/دورك في المؤسسة|Your role in this organisation/)).toBeInTheDocument()
    expect(screen.getByLabelText(/المسمى الوظيفي|Job title/i)).toBeDisabled()
    expect(screen.queryByRole('button', { name: /^حفظ$|^Save$/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /إرسال للمراجعة|Submit for review/i })).toBeNull()
  })

  describe('feature action follows jobs.featured', () => {
    const FEATURE = /تمييز الوظيفة|Feature job/i
    const UNFEATURE = /إلغاء التمييز|^Unfeature$/i
    const published = (overrides = {}) => makeJobEmployer({ status: 'PUBLISHED', is_featured: false, ...overrides })

    it.each(['OWNER', 'RECRUITER'] as const)('shows Feature to a %s whose plan includes it', async (role) => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ my_role: role }))
      vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(published())
      renderApp('/employer/jobs/j-1')
      expect(await screen.findByRole('button', { name: FEATURE })).toBeInTheDocument()
    })

    it.each([
      ['jobs.featured=false', () => billingWith(['jobs.post', 'jobs.application_review'])],
      ['TRIAL plan', () => seededPlan('TRIAL')],
      ['BASIC plan', () => seededPlan('BASIC')],
      ['missing rows', () => makeBilling({ entitlements: [] })],
    ])('hides Feature when the plan does not include it (%s) but keeps the other controls', async (_label, billing) => {
      vi.mocked(jobsApi.getEmployerBilling).mockResolvedValue(billing())
      vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(published())
      renderApp('/employer/jobs/j-1')
      expect(await screen.findByRole('button', { name: /إغلاق|^Close$/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: FEATURE })).toBeNull()
      expect(screen.getByRole('button', { name: /إغلاق|^Close$/i })).toBeInTheDocument()
    })

    it('hides Feature while the billing summary cannot be loaded', async () => {
      vi.mocked(jobsApi.getEmployerBilling).mockRejectedValue(new ApiError(500, 'server_error', 'boom'))
      vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(published())
      renderApp('/employer/jobs/j-1')
      expect(await screen.findByRole('button', { name: /إغلاق|^Close$/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: FEATURE })).toBeNull()
    })

    it('hides the mutation control from a VIEWER regardless of the plan', async () => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ my_role: 'VIEWER' }))
      vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(published())
      renderApp('/employer/jobs/j-1')
      expect(await screen.findByText(/دورك في المؤسسة|Your role in this organisation/)).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: FEATURE })).toBeNull()
      expect(screen.queryByRole('button', { name: UNFEATURE })).toBeNull()
    })

    it.each([
      ['still entitled', () => billingWith(['jobs.post', 'jobs.featured'])],
      ['entitlement lost', () => billingWith(['jobs.post'])],
    ])('keeps Unfeature for an already-featured job (%s) and it still works', async (_label, billing) => {
      vi.mocked(jobsApi.getEmployerBilling).mockResolvedValue(billing())
      vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(published({ is_featured: true }))
      vi.mocked(jobsApi.featureJob).mockResolvedValue(published({ is_featured: false }))
      renderApp('/employer/jobs/j-1')
      const unfeature = await screen.findByRole('button', { name: UNFEATURE })
      expect(screen.queryByRole('button', { name: FEATURE })).toBeNull()
      await userEvent.setup().click(unfeature)
      await waitFor(() => expect(jobsApi.featureJob).toHaveBeenCalledWith('j-1', false))
    })

    it('hides Submit when the plan carries no jobs.post', async () => {
      vi.mocked(jobsApi.getEmployerBilling).mockResolvedValue(billingWith(['jobs.featured']))
      vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(makeJobEmployer())
      renderApp('/employer/jobs/j-1')
      await screen.findByLabelText(/المسمى الوظيفي|Job title/i)
      expect(screen.queryByRole('button', { name: /إرسال للمراجعة|Submit for review/i })).toBeNull()
      expect(screen.getByRole('button', { name: /حفظ المسودة|Save draft/i })).toBeInTheDocument()
    })
  })

  describe('applicants link follows the read gate', () => {
    const APPLICANTS = /المتقدمون|Applicants/i
    const published = () => makeJobEmployer({ status: 'PUBLISHED', applications_count: 2 })

    it.each(['OWNER', 'RECRUITER', 'VIEWER'] as const)('shows the link to a %s of a recruiting organisation with jobs.application_review', async (role) => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner({ my_role: role }))
      vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(published())
      renderApp('/employer/jobs/j-1')
      expect(await screen.findByRole('link', { name: APPLICANTS })).toHaveAttribute('href', '/employer/jobs/j-1/applications')
    })

    it.each([
      ['unverified', () => makeEmployerOwner({ verification_status: 'UNVERIFIED', is_verified: false }), () => billingWith(['jobs.post', 'jobs.application_review'])],
      ['recruitment suspended', () => makeEmployerOwner({ recruitment_status: 'SUSPENDED' }), () => billingWith(['jobs.post', 'jobs.application_review'])],
      ['entitlement disabled', () => makeEmployerOwner(), () => billingWith(['jobs.post'])],
      ['entitlement missing', () => makeEmployerOwner(), () => makeBilling({ entitlements: [] })],
    ])('hides the link when the backend would refuse the list (%s)', async (_label, employer, billing) => {
      vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(employer())
      vi.mocked(jobsApi.getEmployerBilling).mockResolvedValue(billing())
      vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(published())
      renderApp('/employer/jobs/j-1')
      await screen.findByLabelText(/المسمى الوظيفي|Job title/i)
      expect(screen.queryByRole('link', { name: APPLICANTS })).toBeNull()
    })

    it('hides the link while the billing summary is unavailable', async () => {
      vi.mocked(jobsApi.getEmployerBilling).mockRejectedValue(new ApiError(500, 'server_error', 'boom'))
      vi.mocked(jobsApi.getEmployerJob).mockResolvedValue(published())
      renderApp('/employer/jobs/j-1')
      await screen.findByLabelText(/المسمى الوظيفي|Job title/i)
      expect(screen.queryByRole('link', { name: APPLICANTS })).toBeNull()
    })
  })
})
