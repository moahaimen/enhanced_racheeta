import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'

import { ApiError, jobs as jobsApi, reference } from '../../api'
import type { BillingSummary, EmployerOwner, Governorate, JobEmployer, Member, Plan } from '../../api'
import { Alert, ApiActionButton, AsyncPage, Badge, Container, EmptyState, ErrorState, FormActions, Icon, JobStatusBadge, LinkButton, LoadingState, PageHeader, PageStack, Pagination, SectionCard, Select, StatCard, Textarea, TextField, UsageMeter, useFormErrors } from '../../design-system'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'
import { ClientValidationError } from '../validation'
import { EmployerForm } from './EmployerForm'
import styles from './EmployerWorkspacePage.module.css'
import { entitled } from './entitlements'

type Loaded = [EmployerOwner | null, Governorate[]]

/** /employer — organisation onboarding and the recruiting workspace. */
export function EmployerWorkspacePage() {
  const { t } = useTranslation()
  const load = async (signal: AbortSignal): Promise<Loaded> => {
    const employer = await jobsApi.getMyEmployer(signal).catch((e: unknown) => {
      if (e instanceof ApiError && e.status === 404) return null
      throw e
    })
    return [employer, await reference.listGovernorates(undefined, signal)]
  }
  return (
    <Container width="xl">
      <AsyncPage load={load}>
        {([employer, governorates], reload) =>
          employer ? (
            <Workspace employer={employer} governorates={governorates} reload={reload} />
          ) : (
            <Container width="md" style={{ paddingInline: 0 }}>
              <PageHeader eyebrow={<><Icon name="briefcase" size={16} />{t('nav.employer')}</>} title={t('employer.onboardingTitle')} description={t('employer.onboardingIntro')} />
              <div className="card-block">
                <EmployerForm employer={null} governorates={governorates} onSaved={reload} />
              </div>
            </Container>
          )
        }
      </AsyncPage>
    </Container>
  )
}

const JOBS_PAGE_SIZE = 20

const SECTIONS = [
  { id: 'overview', icon: 'sparkle', key: 'overview' },
  { id: 'jobs', icon: 'briefcase', key: 'jobs' },
  { id: 'billing', icon: 'tag', key: 'billing' },
  { id: 'members', icon: 'users', key: 'members' },
  { id: 'organization', icon: 'building', key: 'organization' },
] as const

function Workspace({ employer: initial, governorates, reload }: { employer: EmployerOwner; governorates: Governorate[]; reload: () => void }) {
  const { t } = useTranslation()
  const [employer, setEmployer] = useState(initial)
  const billing = useAsyncData<BillingSummary>((signal) => jobsApi.getEmployerBilling(signal), [])
  const [params, setParams] = useSearchParams()
  const jobsPage = Math.max(1, Number(params.get('jobs_page') ?? '1') || 1)
  const jobs = useAsyncData((signal) => jobsApi.listEmployerJobs('', jobsPage, signal), [jobsPage])
  // Authoritative server count (jobs.active_limit gate), never derived from the visible page.
  const activeJobs = employer.active_jobs
  const isOwner = employer.my_role === 'OWNER'
  // Mirrors the backend CanRecruit rule (OWNER or RECRUITER). VIEWER is read-only; an unknown role gets nothing.
  const canWrite = employer.my_role === 'OWNER' || employer.my_role === 'RECRUITER'
  const canRecruit = employer.verification_status === 'VERIFIED' && employer.recruitment_status === 'ACTIVE'
  // Plan capabilities from the billing summary this page already loads; unknown while loading → hidden.
  const canSearchTalent = entitled(billing.data, 'talent.search')
  const canReviewApplicants = entitled(billing.data, 'jobs.application_review')

  return (
    <>
      <PageHeader
        eyebrow={<><Icon name="briefcase" size={16} />{t('nav.employer')}</>}
        title={employer.name}
        description={t('employer.intro')}
        actions={
          <>
            {canRecruit && canWrite && canSearchTalent ? (
              <LinkButton to="/employer/talent" variant="secondary" leading={<Icon name="search" size={18} />}>
                {t('employer.nav.talent')}
              </LinkButton>
            ) : null}
            {canWrite ? (
              <LinkButton to="/employer/jobs/new" leading={<Icon name="plus" size={18} />}>
                {t('employer.newJob')}
              </LinkButton>
            ) : null}
          </>
        }
      />
      <div className={styles.layout}>
        <nav className={styles.sideNav} aria-label={t('employer.title')}>
          {SECTIONS.map((s) => (
            <a key={s.id} href={`#${s.id}`}>
              <Icon name={s.icon} size={18} />
              {t(`employer.nav.${s.key}`)}
            </a>
          ))}
        </nav>
        <PageStack>
          <SectionCard id="overview" title={t('employer.nav.overview')} headingLevel={2}>
            <div className="cluster" style={{ marginBlockEnd: 'var(--space-4)' }}>
              <Badge tone="brand">{t(`organizationTypes.${employer.organization_type}`)}</Badge>
              <Badge tone={employer.verification_status === 'VERIFIED' ? 'success' : employer.verification_status === 'PENDING' ? 'warning' : 'neutral'} leading={employer.verification_status === 'VERIFIED' ? <Icon name="shieldCheck" size={12} /> : undefined}>
                {t(`verification.${employer.verification_status}`)}
              </Badge>
              {employer.is_recruitment_agency ? <Badge tone="outline">{t('organizationTypes.RECRUITMENT_AGENCY')}</Badge> : null}
              {employer.recruitment_status === 'SUSPENDED' ? <Badge tone="error">{t('employer.recruitmentSuspended')}</Badge> : null}
              <Badge tone="outline">
                {t('employer.myRole')}: {t(`employer.roles.${employer.my_role ?? 'VIEWER'}`)}
              </Badge>
            </div>
            <div className={styles.stats}>
              <StatCard label={t('entitlements.jobs.active_limit')} value={<span data-testid="active-jobs-stat">{activeJobs}</span>} />
              <StatCard label={t('employer.plan')} value={billing.data?.plan ? billing.data.plan.code : <Icon name="clock" size={22} />} hint={billing.data?.subscription ? t(`subscriptionStatus.${billing.data.subscription.status}`) : billing.data?.pending_subscription ? t(`subscriptionStatus.${billing.data.pending_subscription.status}`) : undefined} />
              <StatCard label={t('employer.jobsTitle')} value={jobs.data ? jobs.data.count : <Icon name="clock" size={22} />} />
            </div>
          </SectionCard>

          <VerificationBlock employer={employer} isOwner={isOwner} onChange={setEmployer} />

          <SectionCard id="jobs" title={t('employer.jobsTitle')} headingLevel={2} actions={canWrite ? <LinkButton to="/employer/jobs/new" size="sm" leading={<Icon name="plus" size={16} />}>{t('employer.newJob')}</LinkButton> : undefined}>
            {jobs.loading ? (
              <LoadingState testId="jobs-loading" />
            ) : jobs.error ? (
              <ErrorState error={jobs.error} onRetry={jobs.reload} />
            ) : (jobs.data?.results ?? []).length === 0 ? (
              <EmptyState icon="briefcase" title={t('employer.noJobs')} testId="employer-jobs-empty" />
            ) : (
              <ul className={styles.list}>
                {(jobs.data?.results ?? []).map((job: JobEmployer) => (
                  <li key={job.id} className={styles.row} data-testid="employer-job-row">
                    <div className={styles.rowText}>
                      <div className={styles.rowTitle}>
                        <Link to={`/employer/jobs/${job.id}`}>{job.title}</Link>
                      </div>
                      <div className="text-caption">
                        {t(`professions.${job.profession}`)} · {t('employer.applicantsCount', { count: job.applications_count })}
                      </div>
                    </div>
                    <JobStatusBadge status={job.status} />
                    <div className={styles.rowActions}>
                      {canReviewApplicants ? (
                        <LinkButton to={`/employer/jobs/${job.id}/applications`} variant="ghost" size="sm">
                          {t('employer.applicants')}
                        </LinkButton>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {jobs.data ? (
              <Pagination page={jobsPage} total={Math.max(1, Math.ceil(jobs.data.count / JOBS_PAGE_SIZE))} hasNext={jobs.data.next !== null} hasPrevious={jobs.data.previous !== null} onChange={(next) => setParams(next > 1 ? { jobs_page: String(next) } : {})} />
            ) : null}
          </SectionCard>

          <BillingBlock billing={billing} isOwner={isOwner} />
          <MembersBlock isOwner={isOwner} />

          <SectionCard id="organization" title={t('employer.nav.organization')} headingLevel={2}>
            {isOwner ? <EmployerForm employer={employer} governorates={governorates} onSaved={(e) => { setEmployer({ ...e, my_role: employer.my_role }); reload() }} /> : <p className="text-muted">{employer.description}</p>}
          </SectionCard>
        </PageStack>
      </div>
    </>
  )
}

function VerificationBlock({ employer, isOwner, onChange }: { employer: EmployerOwner; isOwner: boolean; onChange: (e: EmployerOwner) => void }) {
  const { t } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  const canRequest = isOwner && (employer.verification_status === 'UNVERIFIED' || employer.verification_status === 'REJECTED')
  return (
    <SectionCard id="verification" title={t('employer.verification')} description={t('employer.verificationHint')} headingLevel={2}>
      <div className="cluster">
        <span>{t('common.status')}:</span>
        <Badge tone={employer.verification_status === 'VERIFIED' ? 'success' : employer.verification_status === 'PENDING' ? 'warning' : employer.verification_status === 'UNVERIFIED' ? 'neutral' : 'error'}>{t(`verification.${employer.verification_status}`)}</Badge>
      </div>
      {employer.verification_note ? <Alert kind="info" title={t('employer.note')}>{employer.verification_note}</Alert> : null}
      {error ? <Alert kind="error">{error}</Alert> : null}
      {canRequest ? (
        <FormActions>
          <ApiActionButton action={() => jobsApi.requestEmployerVerification()} onSuccess={(e) => { setError(null); onChange({ ...e, my_role: employer.my_role }) }} onError={(e) => setError(toErrorMessage(e))} pendingLabel={t('employer.requesting')} leading={<Icon name="shieldCheck" size={18} />}>
            {t('employer.requestVerification')}
          </ApiActionButton>
        </FormActions>
      ) : null}
    </SectionCard>
  )
}

function BillingBlock({ billing, isOwner }: { billing: ReturnType<typeof useAsyncData<BillingSummary>>; isOwner: boolean }) {
  const { t, i18n } = useTranslation()
  const [plan, setPlan] = useState('')
  const [note, setNote] = useState('')
  const [sent, setSent] = useState(false)
  const errors = useFormErrors(['plan', 'note'] as const)
  const planName = (p: Plan) => (i18n.language.startsWith('ar') ? p.name_ar : p.name_en)
  // A request waiting for an administrator. It grants nothing (entitlements
  // still come from `plan`/`subscription`); it exists so the pending state
  // survives a reload instead of the owner being offered the form again.
  const pending = billing.data?.pending_subscription ?? null
  return (
    <SectionCard id="billing" title={t('employer.nav.billing')} headingLevel={2}>
      {billing.loading ? (
        <LoadingState testId="billing-loading" />
      ) : billing.error ? (
        <ErrorState error={billing.error} onRetry={billing.reload} />
      ) : billing.data ? (
        <>
          <div className="cluster" style={{ marginBlockEnd: 'var(--space-4)' }}>
            <span>{t('employer.plan')}:</span>
            <Badge tone="brand">{billing.data.plan ? planName(billing.data.plan) : '—'}</Badge>
            {billing.data.subscription ? (
              <>
                <Badge tone={billing.data.subscription.status === 'ACTIVE' ? 'success' : 'warning'}>{t(`subscriptionStatus.${billing.data.subscription.status}`)}</Badge>
                {billing.data.subscription.ends_at ? (
                  <span className="text-caption">
                    {t('employer.endsAt')} {new Date(billing.data.subscription.ends_at).toLocaleDateString(i18n.language)}
                  </span>
                ) : null}
              </>
            ) : null}
            {pending ? (
              <Badge tone="warning" data-testid="pending-subscription-badge">
                {planName(pending.plan)} · {t(`subscriptionStatus.${pending.status}`)}
              </Badge>
            ) : null}
          </div>
          <div className={styles.meters} data-testid="usage-meters">
            {billing.data.entitlements.map((e) => (
              <UsageMeter key={e.key} entitlement={e} />
            ))}
          </div>
          {isOwner ? (
            <div style={{ marginBlockStart: 'var(--space-6)' }}>
              <h3 style={{ fontSize: 'var(--text-section)' }}>{t('employer.requestPlan')}</h3>
              <p className="text-secondary" style={{ marginBlock: 'var(--space-2) var(--space-4)' }}>
                {t('employer.requestPlanIntro')}
              </p>
              {sent ? (
                <Alert kind="success">{t('employer.requestSent')}</Alert>
              ) : pending ? (
                <Alert kind="info" testId="pending-request-notice">
                  {t('employer.pendingRequestPlan', { plan: planName(pending.plan) })}
                </Alert>
              ) : billing.data.subscription?.status === 'ACTIVE' ? (
                // The backend refuses a new request while one is ACTIVE (a suspended one may be replaced).
                <Alert kind="info" testId="live-subscription-notice">
                  {t('employer.liveSubscriptionPlan', { plan: planName(billing.data.subscription.plan) })}
                </Alert>
              ) : (
                <form noValidate onSubmit={(e) => e.preventDefault()}>
                  {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
                  <div className={styles.plans} role="radiogroup" aria-label={t('employer.requestPlan')}>
                    {billing.data.requestable_plans.map((p) => (
                      <label key={p.code} className={`${styles.plan} ${plan === p.code ? styles.planSelected : ''}`.trim()}>
                        <input type="radio" name="plan" value={p.code} checked={plan === p.code} onChange={() => setPlan(p.code)} />{' '}
                        <strong>{planName(p)}</strong>
                        <div className="text-caption">{p.price_amount ? `${Number(p.price_amount).toLocaleString(i18n.language)} ${p.price_currency}` : t('employer.priceOnRequest')}</div>
                        <div className="text-caption">
                          {p.entitlements
                            .filter((e) => e.kind === 'LIMIT')
                            .map((e) => `${t(`entitlements.${e.key}`, { defaultValue: e.key })}: ${e.limit === null ? t('common.unlimited') : e.limit}`)
                            .join(' · ')}
                        </div>
                      </label>
                    ))}
                  </div>
                  {errors.fieldErrors.plan ? <Alert kind="error">{errors.fieldErrors.plan}</Alert> : null}
                  <Textarea label={t('employer.planNote')} optional rows={2} value={note} onChange={(e) => setNote(e.target.value)} error={errors.fieldErrors.note} />
                  <FormActions>
                    <ApiActionButton
                      type="submit"
                      action={async () => {
                        if (!plan) {
                          errors.setFieldErrors({ plan: t('validation.required') })
                          throw new ClientValidationError()
                        }
                        return jobsApi.requestPlan(plan, note.trim())
                      }}
                      onSuccess={() => { setSent(true); billing.reload() }}
                      onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }}
                      pendingLabel={t('common.sending')}
                    >
                      {t('employer.requestPlanButton')}
                    </ApiActionButton>
                  </FormActions>
                </form>
              )}
            </div>
          ) : null}
        </>
      ) : null}
    </SectionCard>
  )
}

function MembersBlock({ isOwner }: { isOwner: boolean }) {
  const { t } = useTranslation()
  const members = useAsyncData<Member[]>((signal) => jobsApi.listMembers(signal), [])
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<'RECRUITER' | 'VIEWER'>('RECRUITER')
  const [rowError, setRowError] = useState<string | null>(null)
  const errors = useFormErrors(['email', 'role'] as const)
  return (
    <SectionCard id="members" title={t('employer.members')} headingLevel={2}>
      {rowError ? <Alert kind="error">{rowError}</Alert> : null}
      {members.loading ? (
        <LoadingState />
      ) : members.error ? (
        <ErrorState error={members.error} onRetry={members.reload} />
      ) : (
        <ul className={styles.list}>
          {(members.data ?? []).map((m) => (
            <li key={m.id} className={styles.row} data-testid="member-row">
              <div className={styles.rowText}>
                <span className={styles.rowTitle}>{m.full_name}</span> <Badge tone="outline">{t(`employer.roles.${m.role}`)}</Badge>
              </div>
              {isOwner && m.role !== 'OWNER' ? (
                <ApiActionButton variant="ghost" size="sm" action={() => jobsApi.endMember(m.id)} onSuccess={() => members.reload()} onError={(e) => setRowError(toErrorMessage(e))}>
                  {t('employer.endMember')}
                </ApiActionButton>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {isOwner ? (
        <form noValidate onSubmit={(e) => e.preventDefault()} style={{ marginBlockStart: 'var(--space-4)' }}>
          <h4 className="text-label">{t('employer.addMember')}</h4>
          {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
          <div className="grid-2">
            <TextField label={t('employer.memberEmail')} type="email" dir="ltr" value={email} onChange={(e) => setEmail(e.target.value)} error={errors.fieldErrors.email} />
            <Select label={t('employer.memberRole')} value={role} onChange={(e) => setRole(e.target.value as typeof role)}>
              <option value="RECRUITER">{t('employer.roles.RECRUITER')}</option>
              <option value="VIEWER">{t('employer.roles.VIEWER')}</option>
            </Select>
          </div>
          <FormActions>
            <ApiActionButton
              type="submit"
              action={async () => {
                if (!email.trim()) {
                  errors.setFieldErrors({ email: t('validation.required') })
                  throw new ClientValidationError()
                }
                return jobsApi.addMember(email.trim(), role)
              }}
              onSuccess={() => { setEmail(''); errors.clear(); members.reload() }}
              onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }}
              leading={<Icon name="plus" size={16} />}
            >
              {t('common.add')}
            </ApiActionButton>
          </FormActions>
        </form>
      ) : null}
    </SectionCard>
  )
}
