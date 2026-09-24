import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as jobsApi from '../../api/endpoints/jobs'
import * as referenceApi from '../../api/endpoints/reference'
import { tokenStore } from '../../api/tokens'
import { makeJobEmployer, makeTalentCard, makeTalentDetail, paginated } from '../../test/jobFixtures'
import { baghdad, cardiology } from '../../test/providerFixtures'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

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

  describe('invitation job picker', () => {
    const jobsPage = (page: number, size = 20) =>
      paginated(
        Array.from({ length: size }, (_, i) => makeJobEmployer({ id: `j-${page}-${i}`, title: `Job ${page}-${i}`, status: 'PUBLISHED' })),
        23,
      )
    const invitation = { id: 'inv-1', job: makeJobEmployer(), message: '', status: 'PENDING' as const, expires_at: '2026-10-01T00:00:00Z', created_at: '2026-09-22T00:00:00Z' }

    it('shows the first page of published jobs and loads page 2 on demand with a loading state', async () => {
      vi.mocked(jobsApi.getTalent).mockResolvedValue(makeTalentDetail())
      const second = deferred<ReturnType<typeof jobsPage>>()
      vi.mocked(jobsApi.listEmployerJobs).mockImplementation((_status, page = 1) => {
        if (page === 2) return second.promise
        return Promise.resolve({ ...jobsPage(1), next: 'n', previous: null })
      })
      vi.mocked(jobsApi.inviteCandidate).mockResolvedValue(invitation)
      renderApp('/employer/talent/sp-1')
      const select = await screen.findByLabelText(/الوظيفة|^Job$/i)
      expect(within(select).getAllByRole('option')).toHaveLength(20)
      expect(screen.getByText(/20 من 23|20 of 23/)).toBeInTheDocument()
      const user = userEvent.setup({ delay: null }) // 23 options: skip user-event's per-action timers under CI load
      const more = screen.getByRole('button', { name: /عرض المزيد من الوظائف|Show more jobs/i })
      await user.click(more)
      expect(more).toBeDisabled()
      expect(more).toHaveAttribute('aria-busy', 'true')
      await user.click(more)
      expect(jobsApi.listEmployerJobs).toHaveBeenCalledTimes(2)
      expect(jobsApi.listEmployerJobs).toHaveBeenLastCalledWith('PUBLISHED', 2)
      second.resolve({ ...jobsPage(2, 3), next: null, previous: 'p' })
      await waitFor(() => expect(within(select).getAllByRole('option')).toHaveLength(23))
      expect(screen.queryByRole('button', { name: /عرض المزيد من الوظائف|Show more jobs/i })).toBeNull()
      await user.selectOptions(select, 'j-2-1')
      await user.click(screen.getByRole('button', { name: /إرسال الدعوة|Send invitation/i }))
      await waitFor(() => expect(jobsApi.inviteCandidate).toHaveBeenCalledWith('j-2-1', 'sp-1', ''))
    })

    it('explains when there are no published jobs to invite to', async () => {
      vi.mocked(jobsApi.getTalent).mockResolvedValue(makeTalentDetail())
      vi.mocked(jobsApi.listEmployerJobs).mockResolvedValue(paginated([]))
      renderApp('/employer/talent/sp-1')
      expect(await screen.findByRole('heading', { level: 1, name: 'ممرضة عناية مركزة' })).toBeInTheDocument()
      expect(screen.getByText(/لم تنشئ أي وظيفة بعد|not created any job yet/i)).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /إرسال الدعوة|Send invitation/i })).toBeNull()
    })
  })
})
