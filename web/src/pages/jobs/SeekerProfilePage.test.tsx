import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as jobsApi from '../../api/endpoints/jobs'
import * as referenceApi from '../../api/endpoints/reference'
import { tokenStore } from '../../api/tokens'
import { makeSeekerProfile } from '../../test/jobFixtures'
import { baghdad, cardiology } from '../../test/providerFixtures'
import { makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/jobs')
vi.mock('../../api/endpoints/reference')

describe('SeekerProfilePage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount())
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad])
    vi.mocked(referenceApi.listSpecialties).mockResolvedValue([cardiology])
    vi.mocked(referenceApi.listCities).mockResolvedValue([])
  })

  it('onboards a new seeker: client validation first, then creates the structured résumé', async () => {
    vi.mocked(jobsApi.getMySeekerProfile).mockRejectedValueOnce(new ApiError(404, 'not_found', 'none')).mockResolvedValue(makeSeekerProfile())
    vi.mocked(jobsApi.createMySeekerProfile).mockResolvedValue(makeSeekerProfile())
    renderApp('/jobs/profile')
    expect(await screen.findByRole('heading', { level: 1, name: /أنشئ سيرتك المهنية|Create your résumé/i })).toBeInTheDocument()
    // No file input anywhere: the structured profile is the résumé.
    expect(document.querySelector('input[type="file"]')).toBeNull()

    const user = userEvent.setup()
    const submit = screen.getByRole('button', { name: /إنشاء السيرة|Create résumé/i })
    await user.click(submit)
    expect(jobsApi.createMySeekerProfile).not.toHaveBeenCalled()
    expect(screen.getAllByText(/هذا الحقل مطلوب|required/i).length).toBeGreaterThan(0)

    await user.type(screen.getByLabelText(/المسمى المهني|Professional title/i), 'ممرضة عناية مركزة')
    await user.selectOptions(screen.getByLabelText(/المحافظة$|^Governorate/i), 'g-baghdad')
    await user.click(submit)
    await waitFor(() => expect(jobsApi.createMySeekerProfile).toHaveBeenCalledWith(expect.objectContaining({ professional_title: 'ممرضة عناية مركزة', governorate: 'g-baghdad', profession: 'NURSE' })))
    expect(await screen.findByRole('heading', { level: 1, name: /سيرتي المهنية|My résumé/i })).toBeInTheDocument()
  })

  it('adds a skill to an existing profile and reloads the list', async () => {
    vi.mocked(jobsApi.getMySeekerProfile).mockResolvedValueOnce(makeSeekerProfile()).mockResolvedValueOnce(makeSeekerProfile({ skills: [{ id: 'sk-1', name: 'ICU' }, { id: 'sk-2', name: 'ECG' }] }))
    vi.mocked(jobsApi.addSkill).mockResolvedValue({ id: 'sk-2', name: 'ECG' })
    renderApp('/jobs/profile')
    expect(await screen.findAllByTestId('skill-chip')).toHaveLength(1)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/^المهارة|^Skill$/i), 'ECG')
    await user.click(screen.getByRole('button', { name: /إضافة مهارة|Add skill/i }))
    expect(jobsApi.addSkill).toHaveBeenCalledWith('ECG')
    await waitFor(() => expect(screen.getAllByTestId('skill-chip')).toHaveLength(2))
  })

  it('shows the contact-blocking error on the summary field', async () => {
    vi.mocked(jobsApi.getMySeekerProfile).mockResolvedValue(makeSeekerProfile())
    vi.mocked(jobsApi.updateMySeekerProfile).mockRejectedValue(
      new ApiError(400, 'validation_error', 'Validation failed.', { professional_summary: ['Contact information is not allowed.'] }, { professional_summary: ['contact_information_not_allowed'] }),
    )
    renderApp('/jobs/profile')
    const user = userEvent.setup()
    const summary = await screen.findByLabelText(/نبذة مهنية|Professional summary/i)
    await user.type(summary, ' تواصل عبر test@example.com')
    const [save] = screen.getAllByRole('button', { name: /^حفظ$|^Save$/i })
    if (!save) throw new Error('save button missing')
    await user.click(save)
    expect(await screen.findByText(/لا يُسمح بوضع معلومات اتصال|Direct contact details are not allowed/i)).toBeInTheDocument()
  })
})
