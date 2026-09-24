import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as adminApi from '../../api/endpoints/admin'
import * as authApi from '../../api/endpoints/auth'
import { tokenStore } from '../../api/tokens'
import { makeAdminEmployer, makeAdminJob, makeAdminSubscription, paginated } from '../../test/jobFixtures'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/admin')

describe('AdminConsolePage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ is_staff: true }))
    vi.mocked(adminApi.listEmployers).mockResolvedValue(paginated([makeAdminEmployer()]))
    vi.mocked(adminApi.listJobs).mockResolvedValue(paginated([makeAdminJob({ contact_findings: [{ field: 'description', category: 'PHONE', excerpt: '0770…' }] })]))
    vi.mocked(adminApi.listSubscriptions).mockResolvedValue(paginated([makeAdminSubscription()]))
  })

  it('verifies a pending organisation', async () => {
    vi.mocked(adminApi.setEmployerVerification).mockResolvedValue(makeAdminEmployer({ verification_status: 'VERIFIED', is_verified: true }))
    renderApp('/admin-console')
    const row = await screen.findByTestId('admin-employer')
    expect(within(row).getByText('owner@example.com')).toBeInTheDocument()
    const user = userEvent.setup()
    await user.type(within(row).getByLabelText(/ملاحظة|Note/i), 'تم التحقق من الرخصة')
    await user.click(within(row).getByRole('button', { name: /^توثيق$|^Verify$/i }))
    expect(adminApi.setEmployerVerification).toHaveBeenCalledWith('e-1', 'VERIFIED', 'تم التحقق من الرخصة')
    await waitFor(() => expect(adminApi.listEmployers).toHaveBeenCalledTimes(2))
  })

  it('shows contact findings for a pending job and approves it with the loading contract', async () => {
    const pending = deferred<ReturnType<typeof makeAdminJob>>()
    vi.mocked(adminApi.jobDecision).mockReturnValue(pending.promise)
    renderApp('/admin-console?tab=jobs')
    const row = await screen.findByTestId('admin-job')
    expect(within(row).getByText(/معلومات اتصال محتملة|Possible contact details/i)).toBeInTheDocument()
    expect(adminApi.listJobs).toHaveBeenCalledWith(expect.objectContaining({ status: 'PENDING_ADMIN_REVIEW' }), expect.anything())
    const user = userEvent.setup()
    const approve = within(row).getByRole('button', { name: /موافقة|Approve/i })
    await user.click(approve)
    expect(approve).toBeDisabled()
    await user.click(approve)
    expect(adminApi.jobDecision).toHaveBeenCalledTimes(1)
    expect(adminApi.jobDecision).toHaveBeenCalledWith('j-1', 'approve', '')
    pending.resolve(makeAdminJob({ status: 'PUBLISHED' }))
    await waitFor(() => expect(adminApi.listJobs).toHaveBeenCalledTimes(2))
  })

  it('activates a pending subscription with a term and reference', async () => {
    vi.mocked(adminApi.subscriptionAction).mockResolvedValue(makeAdminSubscription({ status: 'ACTIVE' }))
    renderApp('/admin-console?tab=subscriptions')
    const row = await screen.findByTestId('admin-subscription')
    expect(within(row).getByText(/بانتظار موافقة الإدارة|Pending administrator approval/i)).toBeInTheDocument()
    const user = userEvent.setup()
    await user.type(within(row).getByLabelText(/مرجع الدفع|Payment reference/i), 'TRX-1')
    await user.click(within(row).getByRole('button', { name: /^تفعيل$|^Activate$/i }))
    expect(adminApi.subscriptionAction).toHaveBeenCalledWith('sub-1', 'activate', { reference: 'TRX-1', note: '', term_days: 30 })
    await waitFor(() => expect(adminApi.listSubscriptions).toHaveBeenCalledTimes(2))
  })

  it('grants credits after client validation', async () => {
    vi.mocked(adminApi.grantCredits).mockResolvedValue({ key: 'talent.search_limit', balance: 25 })
    renderApp('/admin-console?tab=credits')
    const form = await screen.findByTestId('credit-form')
    const user = userEvent.setup()
    await user.click(within(form).getByRole('button', { name: /منح الرصيد|Grant credits/i }))
    expect(adminApi.grantCredits).not.toHaveBeenCalled()
    await user.type(within(form).getByLabelText(/معرّف حساب الفوترة|Billing account id/i), 'ba-1')
    await user.selectOptions(within(form).getByLabelText(/نوع الرصيد|Credit type/i), 'talent.search_limit')
    await user.click(within(form).getByRole('button', { name: /منح الرصيد|Grant credits/i }))
    await waitFor(() => expect(adminApi.grantCredits).toHaveBeenCalledWith('ba-1', 'talent.search_limit', 10, ''))
    expect(await within(form).findByText(/25/)).toBeInTheDocument()
  })

  describe('suspended subscriptions', () => {
    beforeEach(() => {
      vi.mocked(adminApi.listSubscriptions).mockResolvedValue(paginated([makeAdminSubscription({ status: 'SUSPENDED' })]))
    })

    it('renders reactivate and cancel, and reactivates through the activate action', async () => {
      const pending = deferred<ReturnType<typeof makeAdminSubscription>>()
      vi.mocked(adminApi.subscriptionAction).mockReturnValue(pending.promise)
      renderApp('/admin-console?tab=subscriptions&filter=SUSPENDED')
      const row = await screen.findByTestId('admin-subscription')
      expect(within(row).getByText(/موقوف|Suspended/)).toBeInTheDocument()
      const reactivate = within(row).getByRole('button', { name: /إعادة التفعيل|Reactivate/i })
      expect(within(row).getByRole('button', { name: /^إلغاء$|^Cancel$/i })).toBeInTheDocument()
      expect(within(row).queryByRole('button', { name: /^إيقاف$|^Suspend$/i })).toBeNull()
      const user = userEvent.setup()
      await user.type(within(row).getByLabelText(/ملاحظة|Note/i), 'دفع المتأخرات')
      await user.click(reactivate)
      expect(reactivate).toBeDisabled()
      expect(reactivate).toHaveAttribute('aria-busy', 'true')
      await user.click(reactivate)
      expect(adminApi.subscriptionAction).toHaveBeenCalledTimes(1)
      expect(adminApi.subscriptionAction).toHaveBeenCalledWith('sub-1', 'activate', { note: 'دفع المتأخرات' })
      pending.resolve(makeAdminSubscription({ status: 'ACTIVE' }))
      await waitFor(() => expect(adminApi.listSubscriptions).toHaveBeenCalledTimes(2))
    })

    it('cancels a suspended subscription', async () => {
      vi.mocked(adminApi.subscriptionAction).mockResolvedValue(makeAdminSubscription({ status: 'CANCELLED' }))
      renderApp('/admin-console?tab=subscriptions&filter=SUSPENDED')
      const row = await screen.findByTestId('admin-subscription')
      const user = userEvent.setup()
      await user.click(within(row).getByRole('button', { name: /^إلغاء$|^Cancel$/i }))
      expect(adminApi.subscriptionAction).toHaveBeenCalledWith('sub-1', 'cancel', { reason: '' })
      await waitFor(() => expect(adminApi.listSubscriptions).toHaveBeenCalledTimes(2))
    })
  })
})
