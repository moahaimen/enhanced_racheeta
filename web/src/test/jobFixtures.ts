import type { AdminEmployer, AdminJob, AdminSubscription } from '../api'
import type { ApplicationEmployer, ApplicationSeeker, BillingSummary, EmployerOwner, EmployerPublic, JobCard, JobEmployer, JobPublic, Plan, SeekerProfile, Subscription, TalentCard, TalentDetail } from '../api'
import { baghdad, cardiology } from './providerFixtures'

export function makeEmployerPublic(overrides: Partial<EmployerPublic> = {}): EmployerPublic {
  return {
    id: 'e-1',
    name: 'مستشفى الأمل',
    organization_type: 'HOSPITAL',
    description: 'مستشفى عام.',
    governorate: baghdad,
    city: null,
    is_recruitment_agency: false,
    is_verified: true,
    provider_profile_id: null,
    ...overrides,
  }
}

export function makeEmployerOwner(overrides: Partial<EmployerOwner> = {}): EmployerOwner {
  return {
    ...makeEmployerPublic(),
    active_jobs: 0,
    verification_status: 'VERIFIED',
    verification_note: '',
    verification_requested_at: null,
    verified_at: '2026-09-01T00:00:00Z',
    recruitment_status: 'ACTIVE',
    is_discoverable: true,
    created_at: '2026-09-01T00:00:00Z',
    my_role: 'OWNER',
    ...overrides,
  }
}

export function makeJobCard(overrides: Partial<JobCard> = {}): JobCard {
  return {
    id: 'j-1',
    title: 'ممرض قسم الطوارئ',
    employer: makeEmployerPublic(),
    hiring_employer: null,
    hiring_organization_name: '',
    profession: 'NURSE',
    general_specialty: cardiology,
    detailed_specialty: '',
    governorate: baghdad,
    city: null,
    employment_type: 'FULL_TIME',
    work_mode: 'ON_SITE',
    shift_type: 'ROTATING',
    minimum_degree: 'BACHELOR',
    minimum_experience_years: 2,
    salary_min: null,
    salary_max: null,
    salary_currency: 'IQD',
    salary_visible: false,
    is_featured: false,
    published_at: '2026-09-20T10:00:00Z',
    application_deadline: null,
    ...overrides,
  }
}

export function makeJobPublic(overrides: Partial<JobPublic> = {}): JobPublic {
  return {
    ...makeJobCard(),
    description: 'العمل ضمن فريق الطوارئ.',
    responsibilities: '',
    requirements: 'إجازة ممارسة سارية.',
    workplace_text: '',
    number_of_openings: 2,
    is_open: true,
    ...overrides,
  }
}

export function makeJobEmployer(overrides: Partial<JobEmployer> = {}): JobEmployer {
  return {
    ...makeJobPublic(),
    status: 'DRAFT',
    moderation_note: '',
    moderation_flags: [],
    featured_until: null,
    submitted_at: null,
    closed_at: null,
    applications_count: 0,
    transitions: [],
    created_at: '2026-09-19T10:00:00Z',
    updated_at: '2026-09-19T10:00:00Z',
    ...overrides,
  }
}

export function makeSeekerProfile(overrides: Partial<SeekerProfile> = {}): SeekerProfile {
  return {
    id: 'sp-1',
    professional_title: 'ممرضة عناية مركزة',
    profession: 'NURSE',
    general_specialty: cardiology,
    detailed_specialty: '',
    degree: 'BACHELOR',
    institution_name: 'جامعة بغداد',
    graduation_year: 2019,
    years_of_experience: 5,
    professional_summary: 'خبرة في العناية المركزة.',
    governorate: baghdad,
    city: null,
    desired_governorate: null,
    employment_preferences: ['FULL_TIME'],
    availability: 'WITHIN_MONTH',
    salary_expectation_min: null,
    salary_currency: 'IQD',
    discoverable_by_employers: true,
    experiences: [],
    education: [],
    skills: [{ id: 'sk-1', name: 'ICU' }],
    languages: [],
    credentials: [],
    created_at: '2026-09-01T00:00:00Z',
    updated_at: '2026-09-01T00:00:00Z',
    ...overrides,
  }
}

export function makeApplicationSeeker(overrides: Partial<ApplicationSeeker> = {}): ApplicationSeeker {
  return {
    id: 'a-1',
    job: makeJobCard(),
    status: 'SUBMITTED',
    cover_text: '',
    snapshot: { professional_title: 'ممرضة عناية مركزة', skills: ['ICU'] },
    submitted_at: '2026-09-21T09:00:00Z',
    transitions: [{ from_status: '', to_status: 'SUBMITTED', reason: '', created_at: '2026-09-21T09:00:00Z' }],
    interviews: [],
    ...overrides,
  }
}

export function makeTalentCard(overrides: Partial<TalentCard> = {}): TalentCard {
  return {
    id: 'sp-1',
    professional_title: 'ممرضة عناية مركزة',
    profession: 'NURSE',
    general_specialty: cardiology,
    detailed_specialty: '',
    degree: 'BACHELOR',
    years_of_experience: 5,
    governorate: baghdad,
    city: null,
    availability: 'WITHIN_MONTH',
    employment_preferences: ['FULL_TIME'],
    skills: ['ICU'],
    languages: [],
    ...overrides,
  }
}

export function makeTalentDetail(overrides: Partial<TalentDetail> = {}): TalentDetail {
  return {
    ...makeTalentCard(),
    institution_name: 'جامعة بغداد',
    graduation_year: 2019,
    professional_summary: 'خبرة في العناية المركزة.',
    desired_governorate: null,
    salary_expectation_min: null,
    salary_currency: 'IQD',
    experiences: [],
    education: [],
    credentials: [],
    is_saved: false,
    ...overrides,
  }
}

export function makeApplicationEmployer(overrides: Partial<ApplicationEmployer> = {}): ApplicationEmployer {
  return {
    id: 'a-1',
    job_id: 'j-1',
    job_title: 'ممرض قسم الطوارئ',
    status: 'SUBMITTED',
    cover_text: 'أرغب بالانضمام.',
    snapshot: { professional_summary: 'خبرة في العناية المركزة.', skills: ['ICU'] },
    candidate: makeTalentCard(),
    submitted_at: '2026-09-21T09:00:00Z',
    transitions: [{ from_status: '', to_status: 'SUBMITTED', reason: '', created_at: '2026-09-21T09:00:00Z' }],
    interviews: [],
    ...overrides,
  }
}

export function makePlan(overrides: Partial<Plan> = {}): Plan {
  return {
    id: 'plan-1',
    code: 'TRIAL',
    audience: 'EMPLOYER',
    name_ar: 'تجريبية',
    name_en: 'Trial',
    description_ar: '',
    description_en: '',
    billing_period: 'NONE',
    term_days: 0,
    price_amount: null,
    price_currency: 'IQD',
    is_default: true,
    entitlements: [{ key: 'jobs.active_limit', kind: 'LIMIT', enabled: true, limit: 1, period: 'NONE' }],
    ...overrides,
  }
}

export function makeSubscription(overrides: Partial<Subscription> = {}): Subscription {
  return {
    id: 'sub-1',
    plan: makePlan({ id: 'plan-2', code: 'PROFESSIONAL', name_ar: 'احترافية', name_en: 'Professional', is_default: false, term_days: 30 }),
    status: 'PENDING',
    requester_note: '',
    starts_at: null,
    ends_at: null,
    created_at: '2026-09-22T00:00:00Z',
    ...overrides,
  }
}

export function makeBilling(overrides: Partial<BillingSummary> = {}): BillingSummary {
  return {
    plan: makePlan(),
    subscription: null,
    pending_subscription: null,
    entitlements: [
      { key: 'jobs.active_limit', kind: 'LIMIT', enabled: true, limit: 1, period: 'NONE', used: 1, credits: 0, remaining: 0 },
      { key: 'talent.search', kind: 'BOOLEAN', enabled: false, limit: null, period: 'NONE', used: 0, credits: 0, remaining: null },
    ],
    requestable_plans: [makePlan({ id: 'plan-2', code: 'PROFESSIONAL', name_ar: 'احترافية', name_en: 'Professional', is_default: false, term_days: 30 })],
    ...overrides,
  }
}

export function makeAdminEmployer(overrides: Partial<AdminEmployer> = {}): AdminEmployer {
  return { ...makeEmployerOwner({ verification_status: 'PENDING', is_verified: false }), created_by_email: 'owner@example.com', active_jobs: 0, provider_profile: null, ...overrides }
}

export function makeAdminJob(overrides: Partial<AdminJob> = {}): AdminJob {
  return { ...makeJobEmployer({ status: 'PENDING_ADMIN_REVIEW' }), contact_findings: [], ...overrides }
}

export function makeAdminSubscription(overrides: Partial<AdminSubscription> = {}): AdminSubscription {
  return {
    id: 'sub-1',
    plan: makePlan({ code: 'PROFESSIONAL', name_ar: 'احترافية', name_en: 'Professional', term_days: 30 }),
    status: 'PENDING',
    requester_note: 'تحويل بنكي 123',
    starts_at: null,
    ends_at: null,
    created_at: '2026-09-22T10:00:00Z',
    billing_account_id: 'ba-1',
    subject_type: 'organization',
    subject_id: 'e-1',
    requested_by_email: 'owner@example.com',
    admin_reference: '',
    admin_note: '',
    events: [],
    payments: [],
    ...overrides,
  }
}

export function paginated<T>(results: T[], count = results.length, next: string | null = null, previous: string | null = null) {
  return { count, next, previous, results }
}
