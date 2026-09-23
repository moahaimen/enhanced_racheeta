import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router'

import { jobs as jobsApi } from '../../api'
import type { ApplicationEmployer, ApplicationStatus } from '../../api'
import { Alert, ApiActionButton, ApplicationStatusBadge, AsyncPage, Badge, Container, EmptyState, FormActions, Icon, PageHeader, PageStack, Pagination, SectionCard, Select, TextField, Textarea, useFormErrors } from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { MessagesThread } from '../jobs/MyApplicationsPage'
import styles from './EmployerWorkspacePage.module.css'

const STATUSES: ApplicationStatus[] = ['SUBMITTED', 'REVIEWING', 'SHORTLISTED', 'INTERVIEW', 'ACCEPTED', 'REJECTED', 'WITHDRAWN']

/** /employer/jobs/:id/applications — applicant review, transitions, interviews, messages. */
export function ApplicantsPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const status = params.get('status') ?? ''
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  return (
    <Container width="xl">
      <AsyncPage load={(signal) => Promise.all([jobsApi.getEmployerJob(id, signal), jobsApi.listJobApplications(id, status, page, signal)])} deps={[id, status, page]}>
        {([job, applications], reload) => (
          <>
            <PageHeader
              eyebrow={
                <Link to={`/employer/jobs/${job.id}`} className="cluster">
                  <Icon name="chevronBack" size={14} flipInRtl /> {job.title}
                </Link>
              }
              title={t('applicants.title')}
              description={t('applicants.intro')}
              actions={
                <Select label={t('common.status')} value={status} onChange={(e) => setParams(e.target.value ? { status: e.target.value } : {})}>
                  <option value="">{t('employer.allStatuses')}</option>
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {t(`applicationStatus.${s}`)}
                    </option>
                  ))}
                </Select>
              }
            />
            <PageStack>
              {applications.results.length === 0 ? (
                <div className="card-block">
                  <EmptyState icon="users" title={t('applicants.empty')} testId="applicants-empty" />
                </div>
              ) : (
                applications.results.map((a) => <ApplicantCard key={a.id} application={a} reload={reload} />)
              )}
              <Pagination page={page} total={Math.max(1, Math.ceil(applications.count / 20))} hasNext={applications.next !== null} hasPrevious={applications.previous !== null} onChange={(p) => setParams({ ...(status ? { status } : {}), page: String(p) })} />
            </PageStack>
          </>
        )}
      </AsyncPage>
    </Container>
  )
}

function ApplicantCard({ application, reload }: { application: ApplicationEmployer; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const [error, setError] = useState<string | null>(null)
  const [reason, setReason] = useState('')
  const [showInterview, setShowInterview] = useState(false)
  const c = application.candidate
  const act = (status: 'REVIEWING' | 'SHORTLISTED' | 'ACCEPTED' | 'REJECTED') => () => jobsApi.transitionApplication(application.id, status, reason.trim())
  const s = application.status
  return (
    <SectionCard
      title={
        <Link to={`/employer/talent/${c.id}`} className={styles.rowTitle} style={{ color: 'inherit', textDecoration: 'none' }}>
          {c.professional_title}
        </Link>
      }
      description={`${t(`professions.${c.profession}`)} · ${t(`degrees.${c.degree}`)} · ${t('talent.experienceYears', { count: c.years_of_experience })} · ${name(c.governorate)}`}
      headingLevel={2}
      actions={<ApplicationStatusBadge status={s} />}
      data-testid="applicant-card"
    >
      {error ? <Alert kind="error">{error}</Alert> : null}
      <div className="grid-2">
        <div>
          {application.cover_text ? (
            <>
              <h4 className="text-label">{t('applicants.cover')}</h4>
              <p className="prewrap text-secondary">{application.cover_text}</p>
            </>
          ) : null}
          <h4 className="text-label" style={{ marginBlockStart: 'var(--space-3)' }}>
            {t('applicants.snapshot')}
          </h4>
          <p className="text-secondary prewrap">{String(application.snapshot.professional_summary ?? '')}</p>
          {Array.isArray(application.snapshot.skills) && (application.snapshot.skills as string[]).length > 0 ? (
            <div className="cluster" style={{ marginBlockStart: 'var(--space-2)' }}>
              {(application.snapshot.skills as string[]).map((sk) => (
                <Badge key={sk} tone="outline">
                  {sk}
                </Badge>
              ))}
            </div>
          ) : null}
          <h4 className="text-label" style={{ marginBlockStart: 'var(--space-3)' }}>
            {t('applicants.history')}
          </h4>
          <ol className="text-caption" style={{ paddingInlineStart: 'var(--space-5)' }}>
            {application.transitions.map((tr, i) => (
              <li key={i}>
                {t(`applicationStatus.${tr.to_status}`)} · {new Date(tr.created_at).toLocaleString(i18n.language)}
                {tr.reason ? ` · ${tr.reason}` : ''}
              </li>
            ))}
          </ol>
          {application.interviews.length > 0 ? (
            <>
              <h4 className="text-label" style={{ marginBlockStart: 'var(--space-3)' }}>
                {t('applicants.interviews')}
              </h4>
              <ul className="text-caption" style={{ paddingInlineStart: 'var(--space-5)' }}>
                {application.interviews.map((iv) => (
                  <li key={iv.id}>
                    {new Date(iv.proposed_at).toLocaleString(i18n.language)} · {t(`applications.interviewModes.${iv.mode}`)} · {t(`applications.interviewStatus.${iv.status}`)}
                    {iv.candidate_response ? ` · ${iv.candidate_response}` : ''}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {['SUBMITTED', 'REVIEWING', 'SHORTLISTED', 'INTERVIEW'].includes(s) ? (
            <div style={{ marginBlockStart: 'var(--space-4)' }}>
              <TextField label={t('applicants.reason')} value={reason} onChange={(e) => setReason(e.target.value)} />
              <div className={styles.rowActions}>
                {s === 'SUBMITTED' ? (
                  <ApiActionButton size="sm" variant="secondary" action={act('REVIEWING')} onSuccess={reload} onError={(e) => setError(toErrorMessage(e))}>
                    {t('applicants.review')}
                  </ApiActionButton>
                ) : null}
                {s === 'SUBMITTED' || s === 'REVIEWING' ? (
                  <ApiActionButton size="sm" action={act('SHORTLISTED')} onSuccess={reload} onError={(e) => setError(toErrorMessage(e))}>
                    {t('applicants.shortlist')}
                  </ApiActionButton>
                ) : null}
                {s === 'SHORTLISTED' || s === 'INTERVIEW' ? (
                  <>
                    <ApiActionButton size="sm" variant="secondary" action={async () => { setShowInterview(true) }} onSuccess={() => undefined}>
                      {t('applicants.interview')}
                    </ApiActionButton>
                    <ApiActionButton size="sm" action={act('ACCEPTED')} onSuccess={reload} onError={(e) => setError(toErrorMessage(e))}>
                      {t('applicants.accept')}
                    </ApiActionButton>
                  </>
                ) : null}
                <ApiActionButton size="sm" variant="danger" action={act('REJECTED')} onSuccess={reload} onError={(e) => setError(toErrorMessage(e))}>
                  {t('applicants.reject')}
                </ApiActionButton>
              </div>
              {showInterview ? <InterviewForm applicationId={application.id} onDone={() => { setShowInterview(false); reload() }} /> : null}
            </div>
          ) : null}
        </div>
        <MessagesThread applicationId={application.id} mySide="EMPLOYER" closed={s === 'WITHDRAWN' || s === 'REJECTED'} />
      </div>
    </SectionCard>
  )
}

function InterviewForm({ applicationId, onDone }: { applicationId: string; onDone: () => void }) {
  const { t } = useTranslation()
  const [at, setAt] = useState('')
  const [mode, setMode] = useState<'IN_PERSON' | 'ONLINE'>('IN_PERSON')
  const [location, setLocation] = useState('')
  const [note, setNote] = useState('')
  const errors = useFormErrors(['proposed_at', 'mode', 'location_text', 'note'] as const)
  return (
    <form noValidate onSubmit={(e) => e.preventDefault()} className="card-block" style={{ marginBlockStart: 'var(--space-3)' }} data-testid="interview-form">
      <h4 className="text-label">{t('applicants.interview')}</h4>
      {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
      <div className="grid-2">
        <TextField label={t('applicants.interviewAt')} type="datetime-local" dir="ltr" value={at} onChange={(e) => setAt(e.target.value)} error={errors.fieldErrors.proposed_at} required />
        <Select label={t('applicants.mode')} value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
          <option value="IN_PERSON">{t('applications.interviewModes.IN_PERSON')}</option>
          <option value="ONLINE">{t('applications.interviewModes.ONLINE')}</option>
        </Select>
      </div>
      <TextField label={t('applicants.location')} optional value={location} onChange={(e) => setLocation(e.target.value)} error={errors.fieldErrors.location_text} />
      <Textarea label={t('applicants.note')} optional rows={2} value={note} onChange={(e) => setNote(e.target.value)} error={errors.fieldErrors.note} />
      <FormActions>
        <ApiActionButton
          type="submit"
          action={async () => {
            if (!at) {
              errors.setFieldErrors({ proposed_at: t('validation.required') })
              throw new Error('validation')
            }
            return jobsApi.requestInterview(applicationId, { proposed_at: new Date(at).toISOString(), mode, location_text: location.trim(), note: note.trim() })
          }}
          onSuccess={onDone}
          onError={(e) => { if (e instanceof Error && e.message === 'validation') return; errors.applyApiError(e) }}
          pendingLabel={t('common.sending')}
        >
          {t('applicants.sendInterview')}
        </ApiActionButton>
      </FormActions>
    </form>
  )
}
