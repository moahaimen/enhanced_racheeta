import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { admin } from '../../api'
import type { AdminEmployer, AdminJob, AdminSubscription } from '../../api'
import type { BadgeTone } from '../../design-system'
import { Alert, ApiActionButton, AsyncPage, Badge, Container, EmptyState, FormActions, Icon, JobStatusBadge, PageHeader, PageStack, Pagination, SectionCard, Select, Tabs, tabPanelProps, TextField, Textarea, useFormErrors } from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { ClientValidationError } from '../validation'
import styles from './AdminConsolePage.module.css'

const TABS = ['employers', 'jobs', 'subscriptions', 'credits'] as const
type Tab = (typeof TABS)[number]

/** /admin-console — Super Admin control plane for recruitment and billing. Staff accounts only. */
export function AdminConsolePage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const raw = params.get('tab')
  const tab: Tab = TABS.includes(raw as Tab) ? (raw as Tab) : 'employers'
  return (
    <Container width="xl">
      <PageHeader eyebrow={<><Icon name="shieldCheck" size={16} />{t('admin.eyebrow')}</>} title={t('admin.title')} description={t('admin.intro')} />
      <Tabs id="admin" aria-label={t('admin.title')} value={tab} onChange={(next) => setParams({ tab: next })} tabs={TABS.map((id) => ({ id, label: t(`admin.tabs.${id}`) }))} />
      <div {...tabPanelProps('admin', tab)}>
        <PageStack>
          {tab === 'employers' ? <EmployersTab /> : tab === 'jobs' ? <JobsTab /> : tab === 'subscriptions' ? <SubscriptionsTab /> : <CreditsTab />}
        </PageStack>
      </div>
    </Container>
  )
}

function usePageParam() {
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const filter = params.get('filter') ?? ''
  const set = (patch: { page?: number; filter?: string }) => {
    const next = new URLSearchParams(params)
    if (patch.filter !== undefined) {
      if (patch.filter) next.set('filter', patch.filter)
      else next.delete('filter')
      next.delete('page')
    }
    if (patch.page !== undefined) {
      if (patch.page > 1) next.set('page', String(patch.page))
      else next.delete('page')
    }
    setParams(next)
  }
  return { page, filter, set }
}

function EmployersTab() {
  const { t } = useTranslation()
  const { page, filter, set } = usePageParam()
  return (
    <SectionCard title={t('admin.tabs.employers')} headingLevel={2}>
      <div className={styles.filters}>
        <Select label={t('admin.verificationFilter')} value={filter} onChange={(e) => set({ filter: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {(['PENDING', 'VERIFIED', 'REJECTED', 'SUSPENDED', 'UNVERIFIED'] as const).map((s) => (
            <option key={s} value={s}>
              {t(`verification.${s}`)}
            </option>
          ))}
        </Select>
      </div>
      <AsyncPage load={(signal) => admin.listEmployers({ verification_status: filter || undefined, page }, signal)} deps={[filter, page]}>
        {(res, reload) => (
          <>
            {res.results.length === 0 ? <EmptyState icon="hospital" title={t('admin.emptyEmployers')} testId="admin-empty-employers" /> : null}
            <ul className={styles.list}>
              {res.results.map((e) => (
                <EmployerRow key={e.id} employer={e} reload={reload} />
              ))}
            </ul>
            <Pagination page={page} total={Math.max(1, Math.ceil(res.count / 20))} hasNext={res.next !== null} hasPrevious={res.previous !== null} onChange={(p) => set({ page: p })} />
          </>
        )}
      </AsyncPage>
    </SectionCard>
  )
}

function EmployerRow({ employer: e, reload }: { employer: AdminEmployer; reload: () => void }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const decide = (status: 'VERIFIED' | 'REJECTED' | 'SUSPENDED' | 'UNVERIFIED') => () => admin.setEmployerVerification(e.id, status, note.trim())
  return (
    <li className={styles.row} data-testid="admin-employer">
      <div className={styles.rowHead}>
        <span className={styles.rowTitle}>{e.name}</span>
        <span className="cluster">
          <Badge tone={e.verification_status === 'VERIFIED' ? 'success' : e.verification_status === 'PENDING' ? 'warning' : e.verification_status === 'UNVERIFIED' ? 'outline' : 'error'}>{t(`verification.${e.verification_status}`)}</Badge>
          {e.recruitment_status === 'SUSPENDED' ? <Badge tone="error">{t('admin.recruitmentSuspended')}</Badge> : null}
        </span>
      </div>
      <dl className={styles.meta}>
        <div>
          <dt>{t('employer.orgType')}</dt>
          <dd>{t(`organizationTypes.${e.organization_type}`)}</dd>
        </div>
        <div>
          <dt>{t('providers.governorate')}</dt>
          <dd>{name(e.governorate)}</dd>
        </div>
        <div>
          <dt>{t('admin.createdBy')}</dt>
          <dd dir="ltr">{e.created_by_email}</dd>
        </div>
        <div>
          <dt>{t('admin.activeJobs')}</dt>
          <dd>{e.active_jobs}</dd>
        </div>
      </dl>
      {e.description ? <p className="text-secondary prewrap">{e.description}</p> : null}
      {e.verification_note ? <p className="text-caption">{t('admin.lastNote')}: {e.verification_note}</p> : null}
      {error ? <Alert kind="error">{error}</Alert> : null}
      <div className={styles.actions}>
        <TextField label={t('admin.note')} value={note} onChange={(ev) => setNote(ev.target.value)} />
        {e.verification_status !== 'VERIFIED' ? (
          <ApiActionButton size="sm" action={decide('VERIFIED')} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))} leading={<Icon name="check" size={16} />}>
            {t('admin.verify')}
          </ApiActionButton>
        ) : null}
        {e.verification_status === 'PENDING' || e.verification_status === 'UNVERIFIED' ? (
          <ApiActionButton size="sm" variant="danger" action={decide('REJECTED')} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))}>
            {t('common.reject')}
          </ApiActionButton>
        ) : null}
        {e.verification_status === 'VERIFIED' ? (
          <ApiActionButton size="sm" variant="danger" action={decide('SUSPENDED')} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))}>
            {t('common.suspend')}
          </ApiActionButton>
        ) : null}
        {e.recruitment_status === 'ACTIVE' ? (
          <ApiActionButton size="sm" variant="ghost" action={() => admin.setEmployerRecruitment(e.id, 'SUSPENDED', note.trim())} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))}>
            {t('admin.suspendRecruitment')}
          </ApiActionButton>
        ) : (
          <ApiActionButton size="sm" variant="ghost" action={() => admin.setEmployerRecruitment(e.id, 'ACTIVE', note.trim())} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))}>
            {t('admin.restoreRecruitment')}
          </ApiActionButton>
        )}
      </div>
    </li>
  )
}

function JobsTab() {
  const { t } = useTranslation()
  const { page, filter, set } = usePageParam()
  const status = filter || 'PENDING_ADMIN_REVIEW'
  return (
    <SectionCard title={t('admin.tabs.jobs')} headingLevel={2}>
      <div className={styles.filters}>
        <Select label={t('common.status')} value={status} onChange={(e) => set({ filter: e.target.value })}>
          {(['PENDING_ADMIN_REVIEW', 'PUBLISHED', 'SUSPENDED', 'REJECTED', 'CLOSED', 'EXPIRED', 'DRAFT', 'ARCHIVED'] as const).map((s) => (
            <option key={s} value={s}>
              {t(`jobStatus.${s}`)}
            </option>
          ))}
        </Select>
      </div>
      <AsyncPage load={(signal) => admin.listJobs({ status, page }, signal)} deps={[status, page]}>
        {(res, reload) => (
          <>
            {res.results.length === 0 ? <EmptyState icon="briefcase" title={t('admin.emptyJobs')} testId="admin-empty-jobs" /> : null}
            <ul className={styles.list}>
              {res.results.map((j) => (
                <JobRow key={j.id} job={j} reload={reload} />
              ))}
            </ul>
            <Pagination page={page} total={Math.max(1, Math.ceil(res.count / 20))} hasNext={res.next !== null} hasPrevious={res.previous !== null} onChange={(p) => set({ page: p })} />
          </>
        )}
      </AsyncPage>
    </SectionCard>
  )
}

function JobRow({ job: j, reload }: { job: AdminJob; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const act = (action: 'approve' | 'reject' | 'suspend' | 'restore') => () => admin.jobDecision(j.id, action, text.trim())
  return (
    <li className={styles.row} data-testid="admin-job">
      <div className={styles.rowHead}>
        <span className={styles.rowTitle}>{j.title}</span>
        <JobStatusBadge status={j.status} />
      </div>
      <dl className={styles.meta}>
        <div>
          <dt>{t('admin.employer')}</dt>
          <dd>{j.employer.name}</dd>
        </div>
        <div>
          <dt>{t('jobEditor.profession')}</dt>
          <dd>{t(`professions.${j.profession}`)}</dd>
        </div>
        <div>
          <dt>{t('providers.governorate')}</dt>
          <dd>{name(j.governorate)}</dd>
        </div>
        <div>
          <dt>{t('admin.submitted')}</dt>
          <dd>{new Date(j.updated_at).toLocaleString(i18n.language)}</dd>
        </div>
      </dl>
      <details>
        <summary>{t('admin.showText')}</summary>
        <p className="prewrap text-secondary">{j.description}</p>
        {j.requirements ? <p className="prewrap text-secondary">{j.requirements}</p> : null}
      </details>
      {j.contact_findings.length > 0 ? (
        <Alert kind="warning" title={t('admin.contactFindings')}>
          <ul>
            {j.contact_findings.map((f, i) => (
              <li key={i}>
                {f.field}: {f.category} — “{f.excerpt}”
              </li>
            ))}
          </ul>
        </Alert>
      ) : null}
      {error ? <Alert kind="error">{error}</Alert> : null}
      <div className={styles.actions}>
        <TextField label={t('admin.reasonOrNote')} value={text} onChange={(ev) => setText(ev.target.value)} />
        {j.status === 'PENDING_ADMIN_REVIEW' ? (
          <>
            <ApiActionButton size="sm" action={act('approve')} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))} leading={<Icon name="check" size={16} />}>
              {t('common.approve')}
            </ApiActionButton>
            <ApiActionButton size="sm" variant="danger" action={act('reject')} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))}>
              {t('common.reject')}
            </ApiActionButton>
          </>
        ) : null}
        {j.status === 'PUBLISHED' ? (
          <ApiActionButton size="sm" variant="danger" action={act('suspend')} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))}>
            {t('common.suspend')}
          </ApiActionButton>
        ) : null}
        {j.status === 'SUSPENDED' ? (
          <ApiActionButton size="sm" action={act('restore')} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))}>
            {t('admin.restore')}
          </ApiActionButton>
        ) : null}
      </div>
    </li>
  )
}

function SubscriptionsTab() {
  const { t } = useTranslation()
  const { page, filter, set } = usePageParam()
  const status = filter || 'PENDING'
  return (
    <SectionCard title={t('admin.tabs.subscriptions')} headingLevel={2}>
      <div className={styles.filters}>
        <Select label={t('common.status')} value={status} onChange={(e) => set({ filter: e.target.value })}>
          {(['PENDING', 'ACTIVE', 'SUSPENDED', 'CANCELLED', 'EXPIRED', 'REJECTED'] as const).map((s) => (
            <option key={s} value={s}>
              {t(`subscriptionStatus.${s}`)}
            </option>
          ))}
        </Select>
      </div>
      <AsyncPage load={(signal) => admin.listSubscriptions({ status, page }, signal)} deps={[status, page]}>
        {(res, reload) => (
          <>
            {res.results.length === 0 ? <EmptyState icon="tag" title={t('admin.emptySubscriptions')} testId="admin-empty-subscriptions" /> : null}
            <ul className={styles.list}>
              {res.results.map((s) => (
                <SubscriptionRow key={s.id} sub={s} reload={reload} />
              ))}
            </ul>
            <Pagination page={page} total={Math.max(1, Math.ceil(res.count / 20))} hasNext={res.next !== null} hasPrevious={res.previous !== null} onChange={(p) => set({ page: p })} />
          </>
        )}
      </AsyncPage>
    </SectionCard>
  )
}

function SubscriptionRow({ sub: s, reload }: { sub: AdminSubscription; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const [reference, setReference] = useState('')
  const [note, setNote] = useState('')
  const [termDays, setTermDays] = useState(String(s.plan.term_days || 30))
  const [error, setError] = useState<string | null>(null)
  const tone: BadgeTone = s.status === 'ACTIVE' ? 'success' : s.status === 'PENDING' ? 'warning' : 'error'
  return (
    <li className={styles.row} data-testid="admin-subscription">
      <div className={styles.rowHead}>
        <span className={styles.rowTitle}>
          {name({ name_ar: s.plan.name_ar, name_en: s.plan.name_en })} · <code dir="ltr">{s.plan.code}</code>
        </span>
        <Badge tone={tone}>{t(`subscriptionStatus.${s.status}`)}</Badge>
      </div>
      <dl className={styles.meta}>
        <div>
          <dt>{t('admin.subject')}</dt>
          <dd dir="ltr">
            {s.subject_type} · {s.subject_id}
          </dd>
        </div>
        <div>
          <dt>{t('admin.requestedBy')}</dt>
          <dd dir="ltr">{s.requested_by_email ?? '—'}</dd>
        </div>
        <div>
          <dt>{t('admin.billingAccount')}</dt>
          <dd dir="ltr">{s.billing_account_id}</dd>
        </div>
        <div>
          <dt>{t('admin.requestedAt')}</dt>
          <dd>{new Date(s.created_at).toLocaleString(i18n.language)}</dd>
        </div>
        {s.ends_at ? (
          <div>
            <dt>{t('employer.endsAt')}</dt>
            <dd>{new Date(s.ends_at).toLocaleDateString(i18n.language)}</dd>
          </div>
        ) : null}
      </dl>
      {s.requester_note ? <p className="text-caption">{t('admin.requesterNote')}: {s.requester_note}</p> : null}
      {s.payments.length > 0 ? (
        <p className="text-caption">
          {t('admin.payments')}: {s.payments.map((p) => `${p.method} ${p.reference || ''} (${t(`admin.paymentStatus.${p.status}`)})`).join(' · ')}
        </p>
      ) : null}
      {error ? <Alert kind="error">{error}</Alert> : null}
      {s.status === 'PENDING' ? (
        <div className={styles.actions}>
          <TextField label={t('admin.paymentReference')} dir="ltr" value={reference} onChange={(e) => setReference(e.target.value)} />
          <TextField label={t('admin.termDays')} dir="ltr" inputMode="numeric" value={termDays} onChange={(e) => setTermDays(e.target.value)} />
          <TextField label={t('admin.note')} value={note} onChange={(e) => setNote(e.target.value)} />
          <ApiActionButton size="sm" action={() => admin.subscriptionAction(s.id, 'activate', { reference: reference.trim(), note: note.trim(), ...(Number(termDays) > 0 ? { term_days: Number(termDays) } : {}) })} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))} leading={<Icon name="check" size={16} />}>
            {t('admin.activate')}
          </ApiActionButton>
          <ApiActionButton size="sm" variant="danger" action={() => admin.subscriptionAction(s.id, 'reject', { reason: note.trim() })} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))}>
            {t('common.reject')}
          </ApiActionButton>
        </div>
      ) : s.status === 'ACTIVE' ? (
        <div className={styles.actions}>
          <TextField label={t('admin.note')} value={note} onChange={(e) => setNote(e.target.value)} />
          <ApiActionButton size="sm" variant="danger" action={() => admin.subscriptionAction(s.id, 'suspend', { reason: note.trim() })} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))}>
            {t('common.suspend')}
          </ApiActionButton>
          <ApiActionButton size="sm" variant="ghost" action={() => admin.subscriptionAction(s.id, 'cancel', { reason: note.trim() })} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))}>
            {t('common.cancel')}
          </ApiActionButton>
        </div>
      ) : s.status === 'SUSPENDED' ? (
        <div className={styles.actions}>
          <TextField label={t('admin.note')} value={note} onChange={(e) => setNote(e.target.value)} />
          <ApiActionButton size="sm" action={() => admin.subscriptionAction(s.id, 'activate', { note: note.trim() })} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))} leading={<Icon name="check" size={16} />}>
            {t('admin.reactivate')}
          </ApiActionButton>
          <ApiActionButton size="sm" variant="ghost" action={() => admin.subscriptionAction(s.id, 'cancel', { reason: note.trim() })} onSuccess={reload} onError={(err) => setError(toErrorMessage(err))}>
            {t('common.cancel')}
          </ApiActionButton>
        </div>
      ) : null}
    </li>
  )
}

const CREDIT_KEYS = ['jobs.active_limit', 'jobs.featured_limit', 'talent.search_limit', 'talent.invite_limit', 'applications.limit'] as const

function CreditsTab() {
  const { t } = useTranslation()
  const [account, setAccount] = useState('')
  const [key, setKey] = useState<string>(CREDIT_KEYS[0])
  const [amount, setAmount] = useState('10')
  const [note, setNote] = useState('')
  const [result, setResult] = useState<{ key: string; balance: number } | null>(null)
  const errors = useFormErrors(['billing_account', 'key', 'amount', 'note'] as const)
  return (
    <SectionCard title={t('admin.tabs.credits')} description={t('admin.creditsIntro')} headingLevel={2}>
      <form noValidate onSubmit={(e) => e.preventDefault()} data-testid="credit-form">
        {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
        {result ? (
          <Alert kind="success">
            {t('admin.creditGranted', { key: t(`entitlements.${result.key}`, { defaultValue: result.key }), balance: result.balance })}
          </Alert>
        ) : null}
        <TextField label={t('admin.billingAccount')} dir="ltr" value={account} onChange={(e) => setAccount(e.target.value)} error={errors.fieldErrors.billing_account} required />
        <div className="grid-2">
          <Select label={t('admin.creditKey')} value={key} onChange={(e) => setKey(e.target.value)} error={errors.fieldErrors.key}>
            {CREDIT_KEYS.map((k) => (
              <option key={k} value={k}>
                {t(`entitlements.${k}`)}
              </option>
            ))}
          </Select>
          <TextField label={t('admin.creditAmount')} dir="ltr" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} error={errors.fieldErrors.amount} required />
        </div>
        <Textarea label={t('admin.note')} optional rows={2} value={note} onChange={(e) => setNote(e.target.value)} error={errors.fieldErrors.note} />
        <FormActions>
          <ApiActionButton
            type="submit"
            action={async () => {
              const next: Record<string, string> = {}
              if (!account.trim()) next.billing_account = t('validation.required')
              if (!/^-?\d+$/.test(amount.trim())) next.amount = t('validation.number')
              errors.setFieldErrors(next)
              errors.setFormError(null)
              if (Object.keys(next).length) throw new ClientValidationError()
              return admin.grantCredits(account.trim(), key, Number(amount), note.trim())
            }}
            onSuccess={setResult}
            onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }}
            pendingLabel={t('common.saving')}
          >
            {t('admin.grant')}
          </ApiActionButton>
        </FormActions>
      </form>
    </SectionCard>
  )
}
