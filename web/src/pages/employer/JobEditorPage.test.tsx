import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as jobsApi from '../../api/endpoints/jobs'
import * as referenceApi from '../../api/endpoints/reference'
import { tokenStore } from '../../api/tokens'
import { makeEmployerOwner, makeEmployerPublic, makeJobEmployer } from '../../test/jobFixtures'
import { baghdad, cardiology } from '../../test/providerFixtures'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/jobs')
vi.mock('../../api/endpoints/reference')

describe('JobEditorPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'MEDICAL_COMPANY' }))
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad])
    vi.mocked(referenceApi.listSpecialties).mockResolvedValue([cardiology])
    vi.mocked(referenceApi.listCities).mockResolvedValue([])
    vi.mocked(jobsApi.getMyEmployer).mockResolvedValue(makeEmployerOwner())
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
})
