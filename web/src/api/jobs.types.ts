/** Jobs, talent and billing types. Mirror docs/api/openapi.yaml. */
import type { City, Governorate, Paginated, Specialty } from './providers.types'

export type Profession =
  | 'DOCTOR'
  | 'DENTIST'
  | 'PHARMACIST'
  | 'NURSE'
  | 'MIDWIFE'
  | 'LAB_TECHNICIAN'
  | 'RADIOLOGY_TECHNICIAN'
  | 'ANESTHESIA_TECHNICIAN'
  | 'PHYSIOTHERAPIST'
  | 'NUTRITIONIST'
  | 'PSYCHOLOGIST'
  | 'MEDICAL_ASSISTANT'
  | 'ADMINISTRATIVE'
  | 'OTHER'
export const PROFESSIONS: Profession[] = ['DOCTOR', 'DENTIST', 'PHARMACIST', 'NURSE', 'MIDWIFE', 'LAB_TECHNICIAN', 'RADIOLOGY_TECHNICIAN', 'ANESTHESIA_TECHNICIAN', 'PHYSIOTHERAPIST', 'NUTRITIONIST', 'PSYCHOLOGIST', 'MEDICAL_ASSISTANT', 'ADMINISTRATIVE', 'OTHER']

export type Degree = 'DIPLOMA' | 'BACHELOR' | 'HIGHER_DIPLOMA' | 'MASTER' | 'PHD' | 'BOARD' | 'OTHER'
export const DEGREES: Degree[] = ['DIPLOMA', 'BACHELOR', 'HIGHER_DIPLOMA', 'MASTER', 'PHD', 'BOARD', 'OTHER']
export type EmploymentType = 'FULL_TIME' | 'PART_TIME' | 'CONTRACT' | 'TEMPORARY' | 'INTERNSHIP' | 'LOCUM'
export const EMPLOYMENT_TYPES: EmploymentType[] = ['FULL_TIME', 'PART_TIME', 'CONTRACT', 'TEMPORARY', 'INTERNSHIP', 'LOCUM']
export type WorkMode = 'ON_SITE' | 'REMOTE' | 'HYBRID'
export const WORK_MODES: WorkMode[] = ['ON_SITE', 'REMOTE', 'HYBRID']
export type ShiftType = 'DAY' | 'NIGHT' | 'ROTATING' | 'FLEXIBLE' | 'ON_CALL'
export const SHIFT_TYPES: ShiftType[] = ['DAY', 'NIGHT', 'ROTATING', 'FLEXIBLE', 'ON_CALL']
export type Availability = 'IMMEDIATE' | 'WITHIN_MONTH' | 'WITHIN_3_MONTHS' | 'NOT_AVAILABLE'
export const AVAILABILITIES: Availability[] = ['IMMEDIATE', 'WITHIN_MONTH', 'WITHIN_3_MONTHS', 'NOT_AVAILABLE']
export type LanguageLevel = 'BASIC' | 'INTERMEDIATE' | 'ADVANCED' | 'NATIVE'
export type OrganizationType = 'HOSPITAL' | 'MEDICAL_CENTER' | 'CLINIC' | 'PHARMACY' | 'LABORATORY' | 'BEAUTY_CENTER' | 'MEDICAL_COMPANY' | 'HEALTHCARE_INSTITUTION' | 'UNIVERSITY' | 'RECRUITMENT_AGENCY' | 'OTHER'
export const ORGANIZATION_TYPES: OrganizationType[] = ['HOSPITAL', 'MEDICAL_CENTER', 'CLINIC', 'PHARMACY', 'LABORATORY', 'BEAUTY_CENTER', 'MEDICAL_COMPANY', 'HEALTHCARE_INSTITUTION', 'UNIVERSITY', 'RECRUITMENT_AGENCY', 'OTHER']
export type EmployerVerificationStatus = 'UNVERIFIED' | 'PENDING' | 'VERIFIED' | 'REJECTED' | 'SUSPENDED'
export type JobStatus = 'DRAFT' | 'PENDING_ADMIN_REVIEW' | 'PUBLISHED' | 'CLOSED' | 'EXPIRED' | 'REJECTED' | 'SUSPENDED' | 'ARCHIVED'
export type ApplicationStatus = 'SUBMITTED' | 'REVIEWING' | 'SHORTLISTED' | 'INTERVIEW' | 'ACCEPTED' | 'REJECTED' | 'WITHDRAWN'
export type InvitationStatus = 'PENDING' | 'ACCEPTED' | 'DECLINED' | 'EXPIRED' | 'CANCELLED'
export type MemberRole = 'OWNER' | 'RECRUITER' | 'VIEWER'

export interface EmployerPublic {
  id: string
  name: string
  organization_type: OrganizationType
  description: string
  governorate: Governorate
  city: City | null
  is_recruitment_agency: boolean
  is_verified: boolean
  provider_profile_id: string | null
}

export interface EmployerOwner extends EmployerPublic {
  /** Server-side count of PENDING_ADMIN_REVIEW + PUBLISHED jobs (the jobs.active_limit gate). */
  active_jobs: number
  verification_status: EmployerVerificationStatus
  verification_note: string
  verification_requested_at: string | null
  verified_at: string | null
  recruitment_status: 'ACTIVE' | 'SUSPENDED'
  is_discoverable: boolean
  created_at: string
  my_role?: MemberRole
}

export interface EmployerWrite {
  name?: string
  organization_type?: OrganizationType
  description?: string
  governorate?: string
  city?: string | null
  provider_profile?: string | null
  is_recruitment_agency?: boolean
  is_discoverable?: boolean
}

export interface Member {
  id: string
  full_name: string
  role: MemberRole
  status: 'ACTIVE' | 'ENDED'
  created_at: string
}

export interface JobCard {
  id: string
  title: string
  employer: EmployerPublic
  hiring_employer: EmployerPublic | null
  hiring_organization_name: string
  profession: Profession
  general_specialty: Specialty | null
  detailed_specialty: string
  governorate: Governorate
  city: City | null
  employment_type: EmploymentType
  work_mode: WorkMode
  shift_type: ShiftType | ''
  minimum_degree: Degree | ''
  minimum_experience_years: number
  salary_min: string | null
  salary_max: string | null
  salary_currency: string
  salary_visible: boolean
  is_featured: boolean
  published_at: string | null
  application_deadline: string | null
}

export interface JobPublic extends JobCard {
  description: string
  responsibilities: string
  requirements: string
  workplace_text: string
  number_of_openings: number
  is_open: boolean
}

export interface JobTransition {
  from_status: string
  to_status: string
  reason: string
  created_at: string
}

export interface JobEmployer extends JobPublic {
  status: JobStatus
  moderation_note: string
  moderation_flags: { field: string; category: string; excerpt: string }[]
  featured_until: string | null
  submitted_at: string | null
  closed_at: string | null
  applications_count: number
  transitions: JobTransition[]
  created_at: string
  updated_at: string
}

export interface JobWrite {
  title?: string
  profession?: Profession
  general_specialty?: string | null
  detailed_specialty?: string
  description?: string
  responsibilities?: string
  requirements?: string
  minimum_degree?: Degree | ''
  minimum_experience_years?: number
  governorate?: string
  city?: string | null
  workplace_text?: string
  employment_type?: EmploymentType
  work_mode?: WorkMode
  shift_type?: ShiftType | ''
  salary_min?: string | null
  salary_max?: string | null
  salary_currency?: string
  salary_visible?: boolean
  number_of_openings?: number
  application_deadline?: string | null
  hiring_employer?: string | null
  hiring_organization_name?: string
}

export interface JobListParams {
  q?: string
  employer?: string
  profession?: Profession | ''
  specialty?: string
  governorate?: string
  city?: string
  degree?: Degree | ''
  min_experience?: number | ''
  max_experience?: number | ''
  employment_type?: EmploymentType | ''
  work_mode?: WorkMode | ''
  shift_type?: ShiftType | ''
  salary_available?: 'true' | ''
  ordering?: string
  page?: number
  page_size?: number
}

export interface WorkExperience {
  id: string
  title: string
  organization_name: string
  governorate: string | null
  start_date: string
  end_date: string | null
  is_current: boolean
  description: string
}
export interface EducationRecord {
  id: string
  degree: Degree
  field_of_study: string
  institution_name: string
  start_year: number | null
  end_year: number | null
}
export interface SkillRecord {
  id: string
  name: string
}
export interface LanguageRecord {
  id: string
  language: string
  level: LanguageLevel
}
export interface CredentialRecord {
  id: string
  kind: 'LICENSE' | 'CERTIFICATION'
  name: string
  issuer: string
  year: number | null
}

export interface SeekerProfile {
  id: string
  professional_title: string
  profession: Profession
  general_specialty: Specialty | null
  detailed_specialty: string
  degree: Degree
  institution_name: string
  graduation_year: number | null
  years_of_experience: number
  professional_summary: string
  governorate: Governorate
  city: City | null
  desired_governorate: Governorate | null
  employment_preferences: EmploymentType[]
  availability: Availability
  salary_expectation_min: string | null
  salary_currency: string
  discoverable_by_employers: boolean
  experiences: WorkExperience[]
  education: EducationRecord[]
  skills: SkillRecord[]
  languages: LanguageRecord[]
  credentials: CredentialRecord[]
  created_at: string
  updated_at: string
}

export interface SeekerProfileWrite {
  professional_title?: string
  profession?: Profession
  general_specialty?: string | null
  detailed_specialty?: string
  degree?: Degree
  institution_name?: string
  graduation_year?: number | null
  years_of_experience?: number
  professional_summary?: string
  governorate?: string
  city?: string | null
  desired_governorate?: string | null
  employment_preferences?: EmploymentType[]
  availability?: Availability
  salary_expectation_min?: string | null
  salary_currency?: string
  discoverable_by_employers?: boolean
}

export interface TalentCard {
  id: string
  professional_title: string
  profession: Profession
  general_specialty: Specialty | null
  detailed_specialty: string
  degree: Degree
  years_of_experience: number
  governorate: Governorate
  city: City | null
  availability: Availability
  employment_preferences: EmploymentType[]
  skills: string[]
  languages: LanguageRecord[]
}

export interface TalentDetail extends TalentCard {
  institution_name: string
  graduation_year: number | null
  professional_summary: string
  desired_governorate: Governorate | null
  salary_expectation_min: string | null
  salary_currency: string
  experiences: WorkExperience[]
  education: EducationRecord[]
  credentials: CredentialRecord[]
  is_saved: boolean
}

export interface TalentParams {
  q?: string
  profession?: Profession | ''
  specialty?: string
  degree?: Degree | ''
  min_experience?: number | ''
  max_experience?: number | ''
  governorate?: string
  city?: string
  skill?: string
  language?: string
  language_level?: string
  availability?: Availability | ''
  employment_type?: EmploymentType | ''
  page?: number
  page_size?: number
}

export interface Interview {
  id: string
  proposed_at: string
  mode: 'IN_PERSON' | 'ONLINE'
  location_text: string
  employer_note: string
  status: 'PROPOSED' | 'ACCEPTED' | 'DECLINED' | 'CANCELLED'
  candidate_response: string
  responded_at: string | null
  created_at: string
}

export interface ApplicationSeeker {
  id: string
  job: JobCard
  status: ApplicationStatus
  cover_text: string
  snapshot: Record<string, unknown>
  submitted_at: string
  transitions: JobTransition[]
  interviews: Interview[]
}

export interface ApplicationEmployer {
  id: string
  job_id: string
  job_title: string
  status: ApplicationStatus
  cover_text: string
  snapshot: Record<string, unknown>
  candidate: TalentCard
  submitted_at: string
  transitions: JobTransition[]
  interviews: Interview[]
}

export interface RecruitmentMessage {
  id: string
  sender_side: 'EMPLOYER' | 'CANDIDATE'
  body: string
  created_at: string
}

export interface SavedCandidate {
  id: string
  candidate: TalentCard
  note: string
  created_at: string
}

export interface Invitation {
  id: string
  job: JobCard
  candidate?: TalentCard
  message: string
  status: InvitationStatus
  responded_at?: string | null
  expires_at: string
  created_at: string
}

// ---- billing --------------------------------------------------------------

export interface PlanEntitlement {
  key: string
  kind: 'BOOLEAN' | 'LIMIT'
  enabled: boolean
  limit: number | null
  period: string
}
export interface Plan {
  id: string
  code: string
  audience: 'EMPLOYER' | 'JOB_SEEKER'
  name_ar: string
  name_en: string
  description_ar: string
  description_en: string
  billing_period: string
  term_days: number
  price_amount: string | null
  price_currency: string
  is_default: boolean
  entitlements: PlanEntitlement[]
}
export interface Entitlement {
  key: string
  kind: 'BOOLEAN' | 'LIMIT'
  enabled: boolean
  limit: number | null
  period: string
  used: number
  credits: number
  remaining: number | null
}
export interface Subscription {
  id: string
  plan: Plan
  status: 'PENDING' | 'ACTIVE' | 'SUSPENDED' | 'CANCELLED' | 'EXPIRED' | 'REJECTED'
  requester_note: string
  starts_at: string | null
  ends_at: string | null
  created_at: string
}
export interface BillingSummary {
  plan: Plan | null
  /** The ACTIVE subscription the entitlements resolve through, or null. */
  subscription: Subscription | null
  /**
   * A plan request waiting for an administrator. Separate from `subscription`
   * on purpose: it never grants an entitlement, it only tells the UI that a
   * request is already in flight (so the request form stays hidden after a
   * reload instead of letting the owner submit a duplicate).
   */
  pending_subscription: Subscription | null
  entitlements: Entitlement[]
  requestable_plans: Plan[]
}

export type { Paginated }
