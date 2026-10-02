import { act, configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as dashboardsApi from '../../api/endpoints/dashboards'
import * as realEstateApi from '../../api/endpoints/realEstate'
import { tokenStore } from '../../api/tokens'
import type {
  AdminDashboard,
  DashboardKey,
  DoctorDashboard,
  FacilityDashboard,
  MedicalCompanyDashboard,
  PatientDashboard,
  RecruiterDashboard,
} from '../../api'
import { changeLanguage } from '../../i18n'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

configure({ asyncUtilTimeout: 5000 })

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/dashboards')
vi.mock('../../api/endpoints/realEstate')

const reservationCounts = { PENDING: 1, CONFIRMED: 2, COMPLETED: 3, REJECTED: 0, CANCELLED: 4, NO_SHOW: 5 }

function brief(id: string, title: string, status: 'PENDING' | 'CONFIRMED' = 'CONFIRMED') {
  return {
    id,
    provider_name_snapshot: 'Dr Noor',
    service_title_snapshot: title,
    starts_at: '2030-01-05T09:00:00Z',
    ends_at: '2030-01-05T09:30:00Z',
    status,
  }
}

const patientData = (title = 'Dental checkup'): PatientDashboard => ({
  reservations: { total: 15, by_status: reservationCounts, upcoming: 3 },
  upcoming: [brief('r1', title)],
  recent: [brief('r2', 'Eye exam', 'PENDING')],
  unread: { notifications: 4, messages: 2 },
})

const providerBase = (): DoctorDashboard => ({
  profile: { display_name: 'Dr Noor', provider_type: 'DOCTOR', verification_status: 'VERIFIED', is_visible: true },
  reservations: { total: 15, by_status: reservationCounts, upcoming: 2 },
  upcoming: [{ ...brief('a1', 'Consultation'), patient_name: 'Layla Hassan' }],
  reviews: { average_rating: 4.5, review_count: 4, distribution: { '1': 0, '2': 0, '3': 1, '4': 1, '5': 2 } },
  offers: { total: 3, running_now: 1, scheduled: 1 },
  unread: { notifications: 0, messages: 1 },
})

const companyData: MedicalCompanyDashboard = {
  verification_status: 'VERIFIED',
  can_publish: true,
  products: { total: 5, active: 3, inactive: 2, exposable: 3 },
  campaigns: { total: 6, draft: 1, pending_payment: 1, active: 2, live: 1, ended: 1, rejected: 1, cancelled: 1 },
  payments: { PENDING: 1, VERIFIED: 2, REJECTED: 1 },
}

const recruiterData = (overrides: Partial<RecruiterDashboard> = {}): RecruiterDashboard => ({
  organization: {
    id: 'o1',
    name: 'Al-Shifa Hospital',
    verification_status: 'VERIFIED',
    recruitment_status: 'ACTIVE',
    can_recruit: true,
    my_role: 'OWNER',
  },
  jobs: {
    total: 6,
    open_now: 2,
    by_status: { DRAFT: 1, PENDING_ADMIN_REVIEW: 1, PUBLISHED: 3, CLOSED: 1, EXPIRED: 0, REJECTED: 0, SUSPENDED: 0, ARCHIVED: 0 },
  },
  applications_access: null,
  applications: {
    total: 8,
    awaiting_review: 2,
    last_7_days: 3,
    by_status: { SUBMITTED: 2, REVIEWING: 1, SHORTLISTED: 1, INTERVIEW: 1, ACCEPTED: 1, REJECTED: 1, WITHDRAWN: 1 },
  },
  interviews: { total: 2, by_status: { PROPOSED: 1, ACCEPTED: 1, DECLINED: 0, CANCELLED: 0 } },
  seats: { active_members: 2, enabled: true, limit: 5 },
  ...overrides,
})

const adminData: AdminDashboard = {
  accounts: {
    total: 12,
    active: 11,
    inactive: 1,
    by_role: { PATIENT: 6, PROVIDER: 3, MEDICAL_COMPANY: 1, REAL_ESTATE_SELLER: 1, ADMIN: 1 },
  },
  providers: { by_verification: { UNVERIFIED: 0, PENDING: 2, VERIFIED: 1, REJECTED: 0, SUSPENDED: 0 } },
  medical_companies: { by_verification: { UNVERIFIED: 0, PENDING: 1, VERIFIED: 0, REJECTED: 0, SUSPENDED: 0 } },
  employers: {
    by_verification: { UNVERIFIED: 1, PENDING: 0, VERIFIED: 2, REJECTED: 0, SUSPENDED: 0 },
    recruitment_suspended: 1,
  },
  jobs: {
    by_status: { DRAFT: 0, PENDING_ADMIN_REVIEW: 4, PUBLISHED: 5, CLOSED: 0, EXPIRED: 0, REJECTED: 0, SUSPENDED: 0, ARCHIVED: 0 },
  },
  reservations: { by_status: reservationCounts },
  marketplace: { products: { total: 9, active: 7 } },
  real_estate: { listings_by_status: { DRAFT: 2, PUBLISHED: 1 } },
  advertising: {
    campaigns_by_status: { DRAFT: 1, PENDING_PAYMENT: 2, ACTIVE: 3, REJECTED: 0, CANCELLED: 0 },
    payments_by_status: { PENDING: 2, VERIFIED: 3, REJECTED: 0 },
  },
  billing: { subscriptions_by_status: { PENDING: 1, ACTIVE: 2, SUSPENDED: 0, CANCELLED: 0, EXPIRED: 0, REJECTED: 0 } },
  audit: { last_24_hours: 14, last_7_days: 90 },
}

function signIn(role: 'PATIENT' | 'PROVIDER' | 'MEDICAL_COMPANY' | 'REAL_ESTATE_SELLER' | 'ADMIN', keys: DashboardKey[], isStaff = false) {
  vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role, is_staff: isStaff }))
  vi.mocked(dashboardsApi.getIndex).mockResolvedValue({ dashboards: keys })
}

describe('Dashboard hub', () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    await changeLanguage('en')
    tokenStore.set({ access: 'a', refresh: 'r' })
  })

  it('shows a loading state, then the patient dashboard with real numbers', async () => {
    signIn('PATIENT', ['patient'])
    const pending = deferred<PatientDashboard>()
    vi.mocked(dashboardsApi.getPatient).mockReturnValue(pending.promise)
    renderApp('/dashboard')

    expect(await screen.findByTestId('async-loading')).toBeInTheDocument()
    await act(async () => pending.resolve(patientData()))

    const dashboard = await screen.findByTestId('dashboard-patient')
    expect(within(dashboard).getByTestId('reservations-total')).toHaveTextContent('15')
    expect(within(dashboard).getByTestId('reservations-upcoming')).toHaveTextContent('3')
    expect(within(dashboard).getByTestId('reservation-CONFIRMED')).toHaveTextContent('2')
    expect(within(dashboard).getByTestId('reservation-NO_SHOW')).toHaveTextContent('5')
    expect(within(within(dashboard).getByTestId('upcoming-list')).getByText('Dental checkup')).toBeInTheDocument()
    expect(within(dashboard).getByTestId('recent-list')).toHaveTextContent('Eye exam')
    expect(within(dashboard).getByTestId('unread-notifications')).toHaveTextContent('4')
    expect(within(dashboard).getByTestId('unread-messages')).toHaveTextContent('2')
    // One dashboard only: no tab list, and nothing else was requested.
    expect(screen.queryByRole('tablist')).toBeNull()
    expect(dashboardsApi.getDoctor).not.toHaveBeenCalled()
    expect(dashboardsApi.getAdmin).not.toHaveBeenCalled()
  })

  it('renders explicit empty states when there is no data', async () => {
    signIn('PATIENT', ['patient'])
    vi.mocked(dashboardsApi.getPatient).mockResolvedValue({
      reservations: { total: 0, by_status: { PENDING: 0, CONFIRMED: 0, COMPLETED: 0, REJECTED: 0, CANCELLED: 0, NO_SHOW: 0 }, upcoming: 0 },
      upcoming: [],
      recent: [],
      unread: { notifications: 0, messages: 0 },
    })
    renderApp('/dashboard')
    expect(await screen.findByTestId('upcoming-list-empty')).toHaveTextContent('No reservations to show')
    expect(screen.getByTestId('recent-list-empty')).toBeInTheDocument()
    expect(screen.getByTestId('reservations-total')).toHaveTextContent('0')
  })

  it('shows an error with retry when the dashboard fails, then recovers', async () => {
    signIn('PATIENT', ['patient'])
    vi.mocked(dashboardsApi.getPatient)
      .mockRejectedValueOnce(new ApiError(500, 'server_error', 'Server exploded'))
      .mockResolvedValue(patientData())
    renderApp('/dashboard')

    expect(await screen.findByTestId('async-error')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(await screen.findByTestId('dashboard-patient')).toBeInTheDocument()
    expect(dashboardsApi.getPatient).toHaveBeenCalledTimes(2)
  })

  it('shows an error when the index itself cannot be loaded', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount())
    vi.mocked(dashboardsApi.getIndex).mockRejectedValue(new ApiError(503, 'unavailable', 'Down'))
    renderApp('/dashboard')
    expect(await screen.findByTestId('async-error')).toBeInTheDocument()
    expect(dashboardsApi.getPatient).not.toHaveBeenCalled()
  })

  it('offers onboarding instead of a dashboard when the server lists none', async () => {
    signIn('PROVIDER', [])
    renderApp('/dashboard')
    expect(await screen.findByTestId('dashboard-none')).toHaveTextContent('No dashboard is available yet')
    const card = screen.getByTestId('dashboard-none').closest('.card-block') as HTMLElement
    expect(within(card).getByRole('link', { name: /my account/i })).toHaveAttribute('href', '/profile')
  })

  it('requires a signed-in account', async () => {
    tokenStore.clear()
    const { router } = renderApp('/dashboard')
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(dashboardsApi.getIndex).not.toHaveBeenCalled()
  })

  it('doctor: rating, upcoming appointments with the patient name, offers', async () => {
    signIn('PROVIDER', ['doctor'])
    vi.mocked(dashboardsApi.getDoctor).mockResolvedValue(providerBase())
    renderApp('/dashboard')
    const dashboard = await screen.findByTestId('dashboard-doctor')
    expect(within(dashboard).getByTestId('rating-average')).toHaveTextContent('4.5')
    expect(within(dashboard).getByTestId('rating-count')).toHaveTextContent('4')
    expect(within(dashboard).getByTestId('stars-5')).toHaveTextContent('2')
    expect(within(dashboard).getByTestId('upcoming-list')).toHaveTextContent('Layla Hassan')
    expect(within(dashboard).getByTestId('offers-running')).toHaveTextContent('1')
    expect(within(dashboard).getByTestId('offers-scheduled')).toHaveTextContent('1')
    expect(within(dashboard).queryByTestId('members-active')).toBeNull()
    expect(within(dashboard).queryByTestId('provider-not-discoverable')).toBeNull()
  })

  it('doctor without reviews says so instead of showing a fabricated rating', async () => {
    signIn('PROVIDER', ['doctor'])
    vi.mocked(dashboardsApi.getDoctor).mockResolvedValue({
      ...providerBase(),
      profile: { display_name: 'Dr New', provider_type: 'DOCTOR', verification_status: 'PENDING', is_visible: true },
      reviews: { average_rating: null, review_count: 0, distribution: { '1': 0, '2': 0, '3': 0, '4': 0, '5': 0 } },
    })
    renderApp('/dashboard')
    expect(await screen.findByTestId('no-reviews')).toHaveTextContent('No reviews yet')
    expect(screen.queryByTestId('rating-average')).toBeNull()
    expect(screen.getByTestId('provider-not-discoverable')).toBeInTheDocument()
  })

  it('facility: shows practitioner membership counts', async () => {
    signIn('PROVIDER', ['facility'])
    const data: FacilityDashboard = {
      ...providerBase(),
      profile: { display_name: 'City Hospital', provider_type: 'HOSPITAL', verification_status: 'VERIFIED', is_visible: true },
      practitioners: { active: 7, incoming_requests: 2, outgoing_invitations: 1 },
    }
    vi.mocked(dashboardsApi.getFacility).mockResolvedValue(data)
    renderApp('/dashboard')
    const dashboard = await screen.findByTestId('dashboard-facility')
    expect(within(dashboard).getByTestId('members-active')).toHaveTextContent('7')
    expect(within(dashboard).getByTestId('members-incoming')).toHaveTextContent('2')
    expect(within(dashboard).getByTestId('members-outgoing')).toHaveTextContent('1')
  })

  it('medical company: products, campaigns and payment status, with no analytics claims', async () => {
    signIn('MEDICAL_COMPANY', ['medical_company'])
    vi.mocked(dashboardsApi.getCompany).mockResolvedValue(companyData)
    renderApp('/dashboard')
    const dashboard = await screen.findByTestId('dashboard-company')
    expect(within(dashboard).getByTestId('products-total')).toHaveTextContent('5')
    expect(within(dashboard).getByTestId('products-exposable')).toHaveTextContent('3')
    expect(within(dashboard).getByTestId('campaigns-live')).toHaveTextContent('1')
    expect(within(dashboard).getByTestId('payment-VERIFIED')).toHaveTextContent('2')
    expect(dashboard).toHaveTextContent(/impressions, clicks and revenue are not tracked/i)
  })

  it('real-estate owner: reuses the existing owner dashboard endpoint', async () => {
    signIn('REAL_ESTATE_SELLER', ['real_estate_owner'])
    vi.mocked(realEstateApi.getOwnerDashboard).mockResolvedValue({
      listings_total: 8,
      listings_draft: 2,
      listings_published: 6,
      listings_visible: 5,
      listings_expired: 1,
      listings_sale: 3,
      listings_rent: 5,
    })
    renderApp('/dashboard')
    const dashboard = await screen.findByTestId('dashboard-owner')
    expect(within(dashboard).getByTestId('listings-total')).toHaveTextContent('8')
    expect(within(dashboard).getByTestId('listings-expired')).toHaveTextContent('1')
    expect(within(dashboard).getByTestId('listings-rent')).toHaveTextContent('5')
    expect(realEstateApi.getOwnerDashboard).toHaveBeenCalledTimes(1)
  })

  it('recruiter: jobs, applications, interviews and seats', async () => {
    signIn('PROVIDER', ['recruiter'])
    vi.mocked(dashboardsApi.getRecruiter).mockResolvedValue(recruiterData())
    renderApp('/dashboard')
    const dashboard = await screen.findByTestId('dashboard-recruiter')
    expect(dashboard).toHaveTextContent('Al-Shifa Hospital')
    expect(within(dashboard).getByTestId('jobs-open')).toHaveTextContent('2')
    expect(within(dashboard).getByTestId('job-PENDING_ADMIN_REVIEW')).toHaveTextContent('1')
    expect(within(dashboard).getByTestId('applications-awaiting')).toHaveTextContent('2')
    expect(within(dashboard).getByTestId('applications-recent')).toHaveTextContent('3')
    expect(within(dashboard).getByTestId('interview-PROPOSED')).toHaveTextContent('1')
    expect(within(dashboard).getByTestId('seats-limit')).toHaveTextContent('5')
  })

  it('recruiter: withheld applicant figures are explained, never shown as zero; unlimited seats', async () => {
    signIn('PROVIDER', ['recruiter'])
    vi.mocked(dashboardsApi.getRecruiter).mockResolvedValue(
      recruiterData({
        applications_access: 'plan_required',
        applications: null,
        interviews: null,
        seats: { active_members: 1, enabled: true, limit: null },
      }),
    )
    renderApp('/dashboard')
    expect(await screen.findByTestId('applications-withheld')).toHaveTextContent(/plan that includes application review/i)
    expect(screen.queryByTestId('applications-total')).toBeNull()
    expect(screen.queryByTestId('interview-PROPOSED')).toBeNull()
    expect(screen.getByTestId('seats-limit')).toHaveTextContent(/unlimited/i)
  })

  it('recruiter: an unverified organisation is told why', async () => {
    signIn('PROVIDER', ['recruiter'])
    vi.mocked(dashboardsApi.getRecruiter).mockResolvedValue(
      recruiterData({
        organization: {
          id: 'o1',
          name: 'New Clinic',
          verification_status: 'PENDING',
          recruitment_status: 'ACTIVE',
          can_recruit: false,
          my_role: 'VIEWER',
        },
        applications_access: 'organization_not_verified',
        applications: null,
        interviews: null,
      }),
    )
    renderApp('/dashboard')
    expect(await screen.findByText(/cannot recruit until it is verified/i)).toBeInTheDocument()
    expect(screen.getByTestId('applications-withheld')).toHaveTextContent(/once your organisation is verified/i)
  })

  it('administrator: aggregate counts only', async () => {
    signIn('ADMIN', ['admin'], true)
    vi.mocked(dashboardsApi.getAdmin).mockResolvedValue(adminData)
    renderApp('/dashboard')
    const dashboard = await screen.findByTestId('dashboard-admin')
    expect(dashboard).toHaveTextContent(/no personal data is shown here/i)
    expect(within(dashboard).getByTestId('accounts-total')).toHaveTextContent('12')
    expect(within(dashboard).getByTestId('provider-PENDING')).toHaveTextContent('2')
    expect(within(dashboard).getByTestId('job-PENDING_ADMIN_REVIEW')).toHaveTextContent('4')
    expect(within(dashboard).getByTestId('audit-24h')).toHaveTextContent('14')
  })

  it('several dashboards: tabs, and only the selected dashboard loads', async () => {
    signIn('PROVIDER', ['facility', 'recruiter'])
    vi.mocked(dashboardsApi.getFacility).mockResolvedValue({
      ...providerBase(),
      practitioners: { active: 1, incoming_requests: 0, outgoing_invitations: 0 },
    })
    vi.mocked(dashboardsApi.getRecruiter).mockResolvedValue(recruiterData())
    renderApp('/dashboard')

    await screen.findByTestId('dashboard-facility')
    expect(screen.getAllByRole('tab').map((tab) => tab.textContent)).toEqual(['Facility', 'Recruiter'])
    expect(dashboardsApi.getRecruiter).not.toHaveBeenCalled() // not requested until opened

    await userEvent.click(screen.getByRole('tab', { name: 'Recruiter' }))
    expect(await screen.findByTestId('dashboard-recruiter')).toBeInTheDocument()
    expect(screen.queryByTestId('dashboard-facility')).toBeNull()
    expect(dashboardsApi.getRecruiter).toHaveBeenCalledTimes(1)
    expect(dashboardsApi.getFacility).toHaveBeenCalledTimes(1) // switching tabs does not refetch the first
  })

  it('never shows a previous account’s data after logout and a different login', async () => {
    signIn('PATIENT', ['patient'])
    const late = deferred<PatientDashboard>()
    vi.mocked(dashboardsApi.getPatient).mockReturnValueOnce(late.promise)
    vi.mocked(authApi.logout).mockImplementation(async () => {
      tokenStore.clear()
    })
    const { router } = renderApp('/dashboard')
    // Account A's dashboard request is in flight (and stays pending).
    await waitFor(() => expect(dashboardsApi.getPatient).toHaveBeenCalledTimes(1))
    expect(screen.queryByTestId('dashboard-patient')).toBeNull()

    await userEvent.click(await screen.findByRole('button', { name: /log out/i }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))

    // Account A's response arrives after A has gone.
    await act(async () => late.resolve(patientData('ACCOUNT A SECRET')))
    expect(screen.queryByText('ACCOUNT A SECRET')).toBeNull()
    expect(screen.queryByTestId('dashboard-patient')).toBeNull()

    // Account B signs in and sees only B's figures.
    vi.mocked(authApi.login).mockResolvedValue({ access: 'b', refresh: 'b' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ id: '22222222-2222-4222-8222-222222222222' }))
    vi.mocked(dashboardsApi.getPatient).mockResolvedValue(patientData('ACCOUNT B VISIT'))
    await userEvent.type(screen.getByLabelText(/email/i), 'b@example.com')
    await userEvent.type(screen.getByLabelText(/^password$/i), 'Str0ng-Passw0rd!{Enter}')
    await waitFor(() => expect(router.state.location.pathname).toBe('/profile'))
    await act(async () => {
      await router.navigate('/dashboard')
    })
    expect(await screen.findByText('ACCOUNT B VISIT')).toBeInTheDocument()
    expect(screen.queryByText('ACCOUNT A SECRET')).toBeNull()
  })

  it('does not poll or refetch on its own', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      signIn('PATIENT', ['patient'])
      vi.mocked(dashboardsApi.getPatient).mockResolvedValue(patientData())
      renderApp('/dashboard')
      await screen.findByTestId('dashboard-patient')
      await act(async () => {
        vi.advanceTimersByTime(10 * 60 * 1000)
      })
      expect(dashboardsApi.getIndex).toHaveBeenCalledTimes(1)
      expect(dashboardsApi.getPatient).toHaveBeenCalledTimes(1)
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('Dashboard navigation and language', () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    await changeLanguage('en')
    tokenStore.set({ access: 'a', refresh: 'r' })
  })

  it('adds a Dashboard link for signed-in accounts only (desktop and mobile)', async () => {
    signIn('PATIENT', ['patient'])
    vi.mocked(dashboardsApi.getPatient).mockResolvedValue(patientData())
    const signedIn = renderApp('/profile')
    const link = await screen.findByRole('link', { name: 'Dashboard' })
    expect(link).toHaveAttribute('href', '/dashboard')
    await userEvent.click(screen.getByRole('button', { name: /open menu/i }))
    expect(screen.getAllByRole('link', { name: 'Dashboard' })).toHaveLength(2)
    signedIn.unmount()

    tokenStore.clear()
    renderApp('/')
    await screen.findAllByRole('link', { name: /create account/i })
    expect(screen.queryByRole('link', { name: 'Dashboard' })).toBeNull()
  })

  it('renders Arabic labels', async () => {
    await changeLanguage('ar')
    signIn('PATIENT', ['patient'])
    vi.mocked(dashboardsApi.getPatient).mockResolvedValue(patientData())
    renderApp('/dashboard')
    const dashboard = await screen.findByTestId('dashboard-patient')
    expect(dashboard).toHaveTextContent('حجوزاتي')
    expect(dashboard).toHaveTextContent('المواعيد القادمة')
    expect(within(dashboard).getByTestId('reservation-CONFIRMED').closest('div')).toHaveTextContent('مؤكد')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('لوحة المعلومات')
  })

  it('renders the Arabic tab names for several dashboards', async () => {
    await changeLanguage('ar')
    signIn('PROVIDER', ['doctor', 'recruiter'])
    vi.mocked(dashboardsApi.getDoctor).mockResolvedValue(providerBase())
    renderApp('/dashboard')
    await screen.findByTestId('dashboard-doctor')
    expect(screen.getAllByRole('tab').map((tab) => tab.textContent)).toEqual(['طبيب', 'مسؤول توظيف'])
  })
})
