import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as jobsApi from '../../api/endpoints/jobs'
import { tokenStore } from '../../api/tokens'
import { makeBilling, makeJobEmployer, makeTalentDetail, paginated } from '../../test/jobFixtures'
import { makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/jobs')

const SAVE = /حفظ المرشح|Save candidate/i
const UNSAVE = /إزالة من المحفوظين|Remove from saved/i
const SEND_INVITE = /إرسال الدعوة|Send invitation/i

function billingWith(flags: Record<string, boolean>) {
  return makeBilling({
    entitlements: Object.entries(flags).map(([key, enabled]) => ({ key, kind: 'BOOLEAN' as const, enabled, limit: null, period: 'NONE' as const, used: 0, credits: 0, remaining: null })),
  })
}

describe('TalentDetailPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'MEDICAL_COMPANY' }))
    vi.mocked(jobsApi.getTalent).mockResolvedValue(makeTalentDetail())
    vi.mocked(jobsApi.listEmployerJobs).mockResolvedValue(paginated([makeJobEmployer({ status: 'PUBLISHED' })]))
  })

  it('shows Save and Invite when the plan carries both capabilities', async () => {
    vi.mocked(jobsApi.getEmployerBilling).mockResolvedValue(billingWith({ 'talent.search': true, 'talent.save_candidate': true, 'talent.invite': true }))
    vi.mocked(jobsApi.saveCandidate).mockResolvedValue({ id: 'sc-1', candidate: makeTalentDetail(), note: '', created_at: '2026-09-25T00:00:00Z' })
    renderApp('/employer/talent/sp-1')
    const save = await screen.findByRole('button', { name: SAVE })
    expect(screen.getByRole('button', { name: SEND_INVITE })).toBeInTheDocument()
    expect(screen.queryByTestId('save-not-included')).toBeNull()
    const user = userEvent.setup()
    await user.click(save)
    await waitFor(() => expect(jobsApi.saveCandidate).toHaveBeenCalledWith('sp-1', ''))
  })

  it('shows Remove when the candidate is already saved', async () => {
    vi.mocked(jobsApi.getEmployerBilling).mockResolvedValue(billingWith({ 'talent.search': true, 'talent.save_candidate': true, 'talent.invite': true }))
    vi.mocked(jobsApi.getTalent).mockResolvedValue(makeTalentDetail({ is_saved: true, saved_candidate_id: 'sc-1' }))
    renderApp('/employer/talent/sp-1')
    expect(await screen.findByRole('button', { name: UNSAVE })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: SAVE })).toBeNull()
  })

  it('hides Save and Remove when talent.save_candidate is disabled, even with talent.search', async () => {
    vi.mocked(jobsApi.getEmployerBilling).mockResolvedValue(billingWith({ 'talent.search': true, 'talent.save_candidate': false, 'talent.invite': true }))
    vi.mocked(jobsApi.getTalent).mockResolvedValue(makeTalentDetail({ is_saved: true, saved_candidate_id: 'sc-1' }))
    renderApp('/employer/talent/sp-1')
    expect(await screen.findByTestId('save-not-included')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: SAVE })).toBeNull()
    expect(screen.queryByRole('button', { name: UNSAVE })).toBeNull()
    // the profile itself is still readable and inviting still works
    expect(screen.getByText('ممرضة عناية مركزة')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: SEND_INVITE })).toBeInTheDocument()
  })

  it('fails closed when the entitlement rows are missing', async () => {
    vi.mocked(jobsApi.getEmployerBilling).mockResolvedValue(billingWith({ 'talent.search': true }))
    renderApp('/employer/talent/sp-1')
    expect(await screen.findByTestId('save-not-included')).toBeInTheDocument()
    expect(screen.getByTestId('invite-not-included')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: SAVE })).toBeNull()
    expect(screen.queryByRole('button', { name: SEND_INVITE })).toBeNull()
  })

  it('keeps the existing permission behaviour for a role the backend refuses', async () => {
    vi.mocked(jobsApi.getEmployerBilling).mockResolvedValue(billingWith({ 'talent.search': true, 'talent.save_candidate': true }))
    vi.mocked(jobsApi.getTalent).mockRejectedValue(new ApiError(403, 'permission_denied', 'Only owners and recruiters can do this.'))
    renderApp('/employer/talent/sp-1')
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: SAVE })).toBeNull()
  })
})
