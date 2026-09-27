import { apiRequest } from '../client'
import type { EmployerOwner, JobEmployer, Paginated, Plan, Subscription } from '../jobs.types'
import { buildQuery } from './providers'

const enc = encodeURIComponent

export interface AdminEmployer extends EmployerOwner {
  created_by_email: string
  active_jobs: number
  /** Linked facility profile, as the reviewer must see it before freezing the identity. */
  provider_profile: { id: string; display_name: string; provider_type: string; verification_status: string } | null
}
export interface AdminJob extends JobEmployer {
  contact_findings: { field: string; category: string; excerpt: string }[]
}
export interface AdminSubscription extends Subscription {
  billing_account_id: string
  subject_type: string
  subject_id: string
  requested_by_email: string | null
  admin_reference: string
  admin_note: string
  events: { from_status: string; to_status: string; actor_email: string | null; reason: string; created_at: string }[]
  payments: { id: string; amount: string | null; currency: string; method: string; reference: string; status: string; note: string; created_at: string }[]
}

export const listEmployers = (params: { verification_status?: string; search?: string; page?: number } = {}, signal?: AbortSignal) => apiRequest<Paginated<AdminEmployer>>(`/api/v1/admin/recruitment/employers${buildQuery(params)}`, { signal })
export const setEmployerVerification = (id: string, status: 'VERIFIED' | 'REJECTED' | 'SUSPENDED' | 'UNVERIFIED', note = '') => apiRequest<AdminEmployer>(`/api/v1/admin/recruitment/employers/${enc(id)}/verification`, { method: 'POST', body: { status, note } })
export const setEmployerRecruitment = (id: string, status: 'ACTIVE' | 'SUSPENDED', reason = '') => apiRequest<AdminEmployer>(`/api/v1/admin/recruitment/employers/${enc(id)}/recruitment/${status}`, { method: 'POST', body: { reason } })
export const listJobs = (params: { status?: string; page?: number } = {}, signal?: AbortSignal) => apiRequest<Paginated<AdminJob>>(`/api/v1/admin/recruitment/jobs${buildQuery(params)}`, { signal })
export const jobDecision = (id: string, action: 'approve' | 'reject' | 'suspend' | 'restore', text = '') => apiRequest<AdminJob>(`/api/v1/admin/recruitment/jobs/${enc(id)}/${action}`, { method: 'POST', body: action === 'reject' || action === 'suspend' ? { reason: text } : { note: text } })
export const listSubscriptions = (params: { status?: string; page?: number } = {}, signal?: AbortSignal) => apiRequest<Paginated<AdminSubscription>>(`/api/v1/admin/billing/subscriptions${buildQuery(params)}`, { signal })
export const subscriptionAction = (id: string, action: 'activate' | 'reject' | 'suspend' | 'cancel', payload: Record<string, unknown> = {}) => apiRequest<AdminSubscription>(`/api/v1/admin/billing/subscriptions/${enc(id)}/${action}`, { method: 'POST', body: payload })
export const grantCredits = (billingAccount: string, key: string, amount: number, note = '') => apiRequest<{ key: string; balance: number }>('/api/v1/admin/billing/credits', { method: 'POST', body: { billing_account: billingAccount, key, amount, note } })
export const listPlans = (audience: string, signal?: AbortSignal) => apiRequest<Plan[]>(`/api/v1/billing/plans?audience=${enc(audience)}`, { auth: false, signal })
