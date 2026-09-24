import { apiRequest } from '../client'
import type {
  ApplicationEmployer,
  ApplicationSeeker,
  BillingSummary,
  CredentialRecord,
  EducationRecord,
  EmployerOwner,
  EmployerPublic,
  EmployerWrite,
  Interview,
  Invitation,
  JobCard,
  JobEmployer,
  JobListParams,
  JobPublic,
  JobWrite,
  LanguageRecord,
  Member,
  Paginated,
  RecruitmentMessage,
  SavedCandidate,
  SeekerProfile,
  SeekerProfileWrite,
  SkillRecord,
  Subscription,
  TalentCard,
  TalentDetail,
  TalentParams,
  WorkExperience,
} from '../jobs.types'
import { buildQuery } from './providers'

const enc = encodeURIComponent

// ---- public ---------------------------------------------------------------
export const listJobs = (params: JobListParams = {}, signal?: AbortSignal) => apiRequest<Paginated<JobCard>>(`/api/v1/jobs${buildQuery(params)}`, { auth: false, signal })
export const getJob = (id: string, signal?: AbortSignal) => apiRequest<JobPublic>(`/api/v1/jobs/${enc(id)}`, { auth: false, signal })
export const getEmployerPublic = (id: string, signal?: AbortSignal) => apiRequest<EmployerPublic>(`/api/v1/employers/${enc(id)}`, { auth: false, signal })

// ---- job seeker -----------------------------------------------------------
export const getMySeekerProfile = (signal?: AbortSignal) => apiRequest<SeekerProfile>('/api/v1/jobs/me/profile', { signal })
export const createMySeekerProfile = (payload: SeekerProfileWrite) => apiRequest<SeekerProfile>('/api/v1/jobs/me/profile', { method: 'POST', body: payload })
export const updateMySeekerProfile = (payload: SeekerProfileWrite) => apiRequest<SeekerProfile>('/api/v1/jobs/me/profile', { method: 'PATCH', body: payload })
export const addExperience = (payload: Omit<WorkExperience, 'id'>) => apiRequest<WorkExperience>('/api/v1/jobs/me/profile/experiences', { method: 'POST', body: payload })
export const deleteExperience = (id: string) => apiRequest<void>(`/api/v1/jobs/me/profile/experiences/${enc(id)}`, { method: 'DELETE' })
export const addEducation = (payload: Omit<EducationRecord, 'id'>) => apiRequest<EducationRecord>('/api/v1/jobs/me/profile/education', { method: 'POST', body: payload })
export const deleteEducation = (id: string) => apiRequest<void>(`/api/v1/jobs/me/profile/education/${enc(id)}`, { method: 'DELETE' })
export const addSkill = (name: string) => apiRequest<SkillRecord>('/api/v1/jobs/me/profile/skills', { method: 'POST', body: { name } })
export const deleteSkill = (id: string) => apiRequest<void>(`/api/v1/jobs/me/profile/skills/${enc(id)}`, { method: 'DELETE' })
export const addLanguage = (payload: Omit<LanguageRecord, 'id'>) => apiRequest<LanguageRecord>('/api/v1/jobs/me/profile/languages', { method: 'POST', body: payload })
export const deleteLanguage = (id: string) => apiRequest<void>(`/api/v1/jobs/me/profile/languages/${enc(id)}`, { method: 'DELETE' })
export const addCredential = (payload: Omit<CredentialRecord, 'id'>) => apiRequest<CredentialRecord>('/api/v1/jobs/me/profile/credentials', { method: 'POST', body: payload })
export const deleteCredential = (id: string) => apiRequest<void>(`/api/v1/jobs/me/profile/credentials/${enc(id)}`, { method: 'DELETE' })
export const applyToJob = (jobId: string, coverText = '') => apiRequest<ApplicationSeeker>(`/api/v1/jobs/${enc(jobId)}/apply`, { method: 'POST', body: { cover_text: coverText } })
export const listMyApplications = (page = 1, signal?: AbortSignal) => apiRequest<Paginated<ApplicationSeeker>>(`/api/v1/jobs/me/applications?page=${page}`, { signal })
export const getMyApplication = (id: string, signal?: AbortSignal) => apiRequest<ApplicationSeeker>(`/api/v1/jobs/me/applications/${enc(id)}`, { signal })
export const withdrawApplication = (id: string, reason = '') => apiRequest<ApplicationSeeker>(`/api/v1/jobs/me/applications/${enc(id)}/withdraw`, { method: 'POST', body: { reason } })
export const respondToInterview = (id: string, accept: boolean, response = '') => apiRequest<Interview>(`/api/v1/jobs/me/interviews/${enc(id)}/respond`, { method: 'POST', body: { accept, response } })
export const listMyInvitations = (page = 1, signal?: AbortSignal) => apiRequest<Paginated<Invitation>>(`/api/v1/jobs/me/invitations?page=${page}`, { signal })
export const respondToInvitation = (id: string, accept: boolean) => apiRequest<Invitation>(`/api/v1/jobs/me/invitations/${enc(id)}/respond`, { method: 'POST', body: { accept } })

// ---- messages (both sides) -------------------------------------------------
export const listMessages = (applicationId: string, signal?: AbortSignal) => apiRequest<RecruitmentMessage[]>(`/api/v1/recruitment/applications/${enc(applicationId)}/messages`, { signal })
export const sendMessage = (applicationId: string, body: string) => apiRequest<RecruitmentMessage>(`/api/v1/recruitment/applications/${enc(applicationId)}/messages`, { method: 'POST', body: { body } })

// ---- employer -------------------------------------------------------------
export const getMyEmployer = (signal?: AbortSignal) => apiRequest<EmployerOwner>('/api/v1/jobs/employer', { signal })
export const createMyEmployer = (payload: EmployerWrite) => apiRequest<EmployerOwner>('/api/v1/jobs/employer', { method: 'POST', body: payload })
export const updateMyEmployer = (payload: EmployerWrite) => apiRequest<EmployerOwner>('/api/v1/jobs/employer', { method: 'PATCH', body: payload })
export const requestEmployerVerification = () => apiRequest<EmployerOwner>('/api/v1/jobs/employer/verification/request', { method: 'POST' })
export const listMembers = (signal?: AbortSignal) => apiRequest<Member[]>('/api/v1/jobs/employer/members', { signal })
export const addMember = (email: string, role: 'RECRUITER' | 'VIEWER') => apiRequest<Member>('/api/v1/jobs/employer/members', { method: 'POST', body: { email, role } })
export const endMember = (id: string) => apiRequest<Member>(`/api/v1/jobs/employer/members/${enc(id)}/end`, { method: 'POST' })
export const getEmployerBilling = (signal?: AbortSignal) => apiRequest<BillingSummary>('/api/v1/jobs/employer/billing', { signal })
export const requestPlan = (plan: string, note = '') => apiRequest<Subscription>('/api/v1/jobs/employer/billing/request', { method: 'POST', body: { plan, note } })
export const listEmployerJobs = (status = '', page = 1, signal?: AbortSignal) => apiRequest<Paginated<JobEmployer>>(`/api/v1/jobs/employer/jobs${buildQuery({ status, page })}`, { signal })
export const getEmployerJob = (id: string, signal?: AbortSignal) => apiRequest<JobEmployer>(`/api/v1/jobs/employer/jobs/${enc(id)}`, { signal })
export const createJob = (payload: JobWrite) => apiRequest<JobEmployer>('/api/v1/jobs/employer/jobs', { method: 'POST', body: payload })
export const updateJob = (id: string, payload: JobWrite) => apiRequest<JobEmployer>(`/api/v1/jobs/employer/jobs/${enc(id)}`, { method: 'PATCH', body: payload })
export const jobAction = (id: string, action: 'submit' | 'close' | 'archive', reason = '') => apiRequest<JobEmployer>(`/api/v1/jobs/employer/jobs/${enc(id)}/${action}`, { method: 'POST', body: { reason } })
export const featureJob = (id: string, featured: boolean) => apiRequest<JobEmployer>(`/api/v1/jobs/employer/jobs/${enc(id)}/feature`, { method: 'POST', body: { featured } })
export const listJobApplications = (jobId: string, status = '', page = 1, signal?: AbortSignal) => apiRequest<Paginated<ApplicationEmployer>>(`/api/v1/jobs/employer/jobs/${enc(jobId)}/applications${buildQuery({ status, page })}`, { signal })
export const getEmployerApplication = (id: string, signal?: AbortSignal) => apiRequest<ApplicationEmployer>(`/api/v1/jobs/employer/applications/${enc(id)}`, { signal })
export const transitionApplication = (id: string, status: 'REVIEWING' | 'SHORTLISTED' | 'ACCEPTED' | 'REJECTED', reason = '') => apiRequest<ApplicationEmployer>(`/api/v1/jobs/employer/applications/${enc(id)}/transition`, { method: 'POST', body: { status, reason } })
export const requestInterview = (id: string, payload: { proposed_at: string; mode: 'IN_PERSON' | 'ONLINE'; location_text?: string; note?: string }) => apiRequest<Interview>(`/api/v1/jobs/employer/applications/${enc(id)}/interviews`, { method: 'POST', body: payload })

// ---- talent ----------------------------------------------------------------
export const searchTalent = (params: TalentParams = {}, signal?: AbortSignal) => apiRequest<Paginated<TalentCard>>(`/api/v1/talent${buildQuery(params)}`, { signal })
export const getTalent = (id: string, signal?: AbortSignal) => apiRequest<TalentDetail>(`/api/v1/talent/${enc(id)}`, { signal })
export const listSaved = (signal?: AbortSignal) => apiRequest<SavedCandidate[]>('/api/v1/talent/saved', { signal })
export const saveCandidate = (jobSeeker: string, note = '') => apiRequest<SavedCandidate>('/api/v1/talent/saved', { method: 'POST', body: { job_seeker: jobSeeker, note } })
export const unsaveCandidate = (id: string) => apiRequest<void>(`/api/v1/talent/saved/${enc(id)}`, { method: 'DELETE' })
export const listInvitations = (signal?: AbortSignal) => apiRequest<Invitation[]>('/api/v1/talent/invitations', { signal })
export const inviteCandidate = (job: string, jobSeeker: string, message = '') => apiRequest<Invitation>('/api/v1/talent/invitations', { method: 'POST', body: { job, job_seeker: jobSeeker, message } })
export const cancelInvitation = (id: string) => apiRequest<Invitation>(`/api/v1/talent/invitations/${enc(id)}/cancel`, { method: 'POST' })
