import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as jobsApi from '../../api/endpoints/jobs'
import * as referenceApi from '../../api/endpoints/reference'
import { tokenStore } from '../../api/tokens'
import { makeJobEmployer, makeTalentCard, makeTalentDetail, paginated } from '../../test/jobFixtures'
import { baghdad, cardiology } from '../../test/providerFixtures'
import { makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/jobs')
vi.mock('../../api/endpoints/reference')

describe('Talent search', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'MEDICAL_COMPANY' }))
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad])
    vi.mocked(referenceApi.listSpecialties).mockResolvedValue([cardiology])
  })

  it('lists candidates with professional facts only and explains the billing rule', async () => {
    vi.mocked(jobsApi.searchTalent).mockResolvedValue(paginated([makeTalentCard()]))
    renderApp('/employer/talent?profession=NURSE')
    expect(await screen.findByRole('link', { name: 'ممرضة عناية مركزة' })).toHaveAttribute('href', '/employer/talent/sp-1')
    expect(jobsApi.searchTalent).toHaveBeenCalledWith(expect.objectContaining({ profession: 'NURSE' }), expect.anything())
    expect(screen.getByText(/يُحتسب البحث مرة واحدة|charged once per filter set/i)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/@|\+964|07\d{9}/)
  })

  it('surfaces the entitlement error when the plan has no talent search', async () => {
    vi.mocked(jobsApi.searchTalent).mockRejectedValue(new ApiError(402, 'entitlement_required', 'no', undefined, undefined, { key: 'talent.search' }))
    renderApp('/employer/talent')
    expect(await screen.findByText(/خطتك الحالية لا تشمل|does not include this feature/i)).toBeInTheDocument()
  })

  it('shows a candidate and sends an invitation for a published job', async () => {
    vi.mocked(jobsApi.getTalent).mockResolvedValue(makeTalentDetail())
    vi.mocked(jobsApi.listEmployerJobs).mockResolvedValue(paginated([makeJobEmployer({ status: 'PUBLISHED' })]))
    vi.mocked(jobsApi.inviteCandidate).mockResolvedValue({ id: 'inv-1', job: makeJobEmployer(), message: '', status: 'PENDING', expires_at: '2026-10-01T00:00:00Z', created_at: '2026-09-22T00:00:00Z' })
    renderApp('/employer/talent/sp-1')
    expect(await screen.findByRole('heading', { level: 1, name: 'ممرضة عناية مركزة' })).toBeInTheDocument()
    expect(jobsApi.listEmployerJobs).toHaveBeenCalledWith('PUBLISHED', 1, expect.anything())
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /إرسال الدعوة|Send invitation/i }))
    await waitFor(() => expect(jobsApi.inviteCandidate).toHaveBeenCalledWith('j-1', 'sp-1', ''))
    expect(await screen.findByText(/أُرسلت الدعوة|Invitation sent/i)).toBeInTheDocument()
  })
})
