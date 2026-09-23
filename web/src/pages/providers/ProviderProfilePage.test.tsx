import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as providersApi from '../../api/endpoints/providers'
import * as referenceApi from '../../api/endpoints/reference'
import { tokenStore } from '../../api/tokens'
import { baghdad, basra, cardiology, dentistry, makeOwner } from '../../test/providerFixtures'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/providers')
vi.mock('../../api/endpoints/reference')

describe('ProviderProfilePage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PROVIDER' }))
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad, basra])
    vi.mocked(referenceApi.listSpecialties).mockResolvedValue([cardiology, dentistry])
    vi.mocked(referenceApi.listCities).mockResolvedValue([])
    vi.mocked(providersApi.listMyServices).mockResolvedValue([])
    vi.mocked(providersApi.listMyMemberships).mockResolvedValue([])
  })

  it('is denied for non-provider roles', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PATIENT' }))
    renderApp('/provider/profile')
    expect(await screen.findByTestId('role-denied')).toBeInTheDocument()
    expect(providersApi.getMyProvider).not.toHaveBeenCalled()
  })

  it('shows onboarding when no profile exists and creates one with loading state', async () => {
    vi.mocked(providersApi.getMyProvider)
      .mockRejectedValueOnce(new ApiError(404, 'not_found', 'none'))
      .mockResolvedValueOnce(makeOwner({ display_name: 'Created Clinic' }))
    const pending = deferred<ReturnType<typeof makeOwner>>()
    vi.mocked(providersApi.createMyProvider).mockReturnValue(pending.promise)

    renderApp('/provider/profile')
    expect(await screen.findByRole('heading', { name: /أكمل ملفك المهني|complete your provider profile/i })).toBeInTheDocument()

    const submit = screen.getByRole('button', { name: /إنشاء الملف المهني|create provider profile/i })
    await userEvent.click(submit) // client validation: name + governorate missing
    expect(await screen.findAllByRole('alert')).toHaveLength(2)
    expect(providersApi.createMyProvider).not.toHaveBeenCalled()

    await userEvent.type(screen.getByLabelText(/الاسم المعروض|display name/i), 'Created Clinic')
    await userEvent.selectOptions(screen.getByLabelText(/المحافظة|governorate/i), baghdad.id)
    await userEvent.selectOptions(screen.getByLabelText(/^النوع$|^type$/i), 'MEDICAL_CENTER')
    await userEvent.click(screen.getByLabelText('طب الأسنان'))
    await userEvent.click(submit)

    expect(submit).toBeDisabled()
    expect(within(submit).getByRole('status')).toBeInTheDocument()
    await userEvent.click(submit)
    expect(providersApi.createMyProvider).toHaveBeenCalledTimes(1)
    expect(vi.mocked(providersApi.createMyProvider).mock.calls[0]![0]).toMatchObject({
      provider_type: 'MEDICAL_CENTER',
      display_name: 'Created Clinic',
      governorate: baghdad.id,
      specialty_ids: [dentistry.id],
    })

    pending.resolve(makeOwner({ display_name: 'Created Clinic' }))
    expect(await screen.findByRole('heading', { name: /ملفي المهني|my provider profile/i })).toBeInTheDocument()
    expect(screen.getByDisplayValue('Created Clinic')).toBeInTheDocument()
  })

  it('loads the existing profile and saves edits through PATCH', async () => {
    vi.mocked(providersApi.getMyProvider).mockResolvedValue(makeOwner({ display_name: 'Loaded', verification_status: 'VERIFIED', can_change_type: false }))
    vi.mocked(providersApi.updateMyProvider).mockResolvedValue(makeOwner({ display_name: 'Edited', verification_status: 'VERIFIED', can_change_type: false }))
    renderApp('/provider/profile')
    const name = await screen.findByDisplayValue('Loaded')
    expect(screen.getByLabelText(/^النوع$|^type$/i)).toBeDisabled() // locked after verification
    await userEvent.clear(name)
    await userEvent.type(name, 'Edited')
    const save = screen.getByRole('button', { name: /^حفظ$|^save$/i })
    await userEvent.click(save)
    await waitFor(() => expect(providersApi.updateMyProvider).toHaveBeenCalledTimes(1))
    const payload = vi.mocked(providersApi.updateMyProvider).mock.calls[0]![0]
    expect(payload.display_name).toBe('Edited')
    expect(payload).not.toHaveProperty('provider_type')
    expect(payload).not.toHaveProperty('verification_status')
    expect(await screen.findByText(/تم حفظ الملف|profile saved/i)).toBeInTheDocument()
  })

  it('maps backend field errors and restores the button', async () => {
    vi.mocked(providersApi.getMyProvider).mockResolvedValue(makeOwner())
    vi.mocked(providersApi.updateMyProvider).mockRejectedValue(
      new ApiError(400, 'validation_error', 'Validation failed.', { city: ['This city does not belong to the selected governorate.'] }),
    )
    renderApp('/provider/profile')
    await screen.findByDisplayValue('Dr Example')
    const save = screen.getByRole('button', { name: /^حفظ$|^save$/i })
    await userEvent.click(save)
    expect(await screen.findByRole('alert')).toHaveTextContent('does not belong')
    expect(save).toBeEnabled()
  })

  it('requests verification with loading state', async () => {
    vi.mocked(providersApi.getMyProvider).mockResolvedValue(makeOwner({ verification_status: 'UNVERIFIED' }))
    const pending = deferred<ReturnType<typeof makeOwner>>()
    vi.mocked(providersApi.requestVerification).mockReturnValue(pending.promise)
    renderApp('/provider/profile')
    const button = await screen.findByRole('button', { name: /طلب التوثيق|request verification/i })
    await userEvent.click(button)
    expect(button).toBeDisabled()
    await userEvent.click(button)
    expect(providersApi.requestVerification).toHaveBeenCalledTimes(1)
    pending.resolve(makeOwner({ verification_status: 'PENDING' }))
    expect(await screen.findByText(/قيد المراجعة|pending review/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /طلب التوثيق|request verification/i })).toBeNull()
  })

  it('lists services, adds one, toggles and deletes with loading state', async () => {
    vi.mocked(providersApi.getMyProvider).mockResolvedValue(makeOwner())
    const service = {
      id: 'svc-1',
      title: 'Consultation',
      description: '',
      specialty: null,
      price: '25000.00',
      currency: 'IQD',
      duration_minutes: 30,
      is_active: true,
      created_at: '',
      updated_at: '',
    }
    vi.mocked(providersApi.listMyServices).mockResolvedValueOnce([]).mockResolvedValue([service])
    const creating = deferred<typeof service>()
    vi.mocked(providersApi.createMyService).mockReturnValue(creating.promise)
    vi.mocked(providersApi.updateMyService).mockResolvedValue({ ...service, is_active: false })
    vi.mocked(providersApi.deleteMyService).mockResolvedValue(undefined)

    renderApp('/provider/profile')
    expect(await screen.findByTestId('services-empty')).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText(/اسم الخدمة|service title/i), 'Consultation')
    await userEvent.type(screen.getByLabelText(/^السعر$|^price$/i), '25000')
    const add = screen.getByRole('button', { name: /^إضافة$|^add$/i })
    await userEvent.click(add)
    expect(add).toBeDisabled()
    await userEvent.click(add)
    expect(providersApi.createMyService).toHaveBeenCalledTimes(1)
    expect(vi.mocked(providersApi.createMyService).mock.calls[0]![0]).toMatchObject({
      title: 'Consultation',
      price: '25000',
      currency: 'IQD',
    })
    creating.resolve(service)
    const row = await screen.findByTestId('service-row')
    expect(row).toHaveTextContent('Consultation')

    await userEvent.click(within(row).getByRole('button', { name: /نشطة|active/i }))
    await waitFor(() => expect(providersApi.updateMyService).toHaveBeenCalledWith('svc-1', { is_active: false }))
    await userEvent.click(within(row).getByRole('button', { name: /حذف|delete/i }))
    await waitFor(() => expect(providersApi.deleteMyService).toHaveBeenCalledWith('svc-1'))
  })

  it('shows memberships and lets the counterpart accept', async () => {
    vi.mocked(providersApi.getMyProvider).mockResolvedValue(makeOwner({ provider_type: 'HOSPITAL', kind: 'FACILITY' }))
    vi.mocked(providersApi.listMyMemberships).mockResolvedValue([
      {
        id: 'm-1',
        practitioner: { id: 'p-doc', provider_type: 'DOCTOR', kind: 'PRACTITIONER', display_name: 'Dr Doc', image_url: '' },
        facility: { id: 'p-1', provider_type: 'HOSPITAL', kind: 'FACILITY', display_name: 'Hosp', image_url: '' },
        status: 'PENDING',
        initiated_by: 'PRACTITIONER',
        role_title: 'Cardiologist',
        my_side: 'FACILITY',
        can_accept: true,
        responded_at: null,
        joined_at: null,
        ended_at: null,
        created_at: '',
      },
    ])
    vi.mocked(providersApi.membershipAction).mockResolvedValue({} as never)
    renderApp('/provider/profile')
    const row = await screen.findByTestId('membership-row')
    expect(row).toHaveTextContent('Dr Doc')
    await userEvent.click(within(row).getByRole('button', { name: /^قبول$|^accept$/i }))
    await waitFor(() => expect(providersApi.membershipAction).toHaveBeenCalledWith('m-1', 'accept'))
  })

  it('shows the services error state', async () => {
    vi.mocked(providersApi.getMyProvider).mockResolvedValue(makeOwner())
    vi.mocked(providersApi.listMyServices).mockRejectedValue(new ApiError(0, 'network_error', 'offline'))
    renderApp('/provider/profile')
    const alerts = await screen.findAllByRole('alert')
    expect(alerts.some((a) => a.textContent?.includes('offline'))).toBe(true)
  })
})
