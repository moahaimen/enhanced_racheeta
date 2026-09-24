import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'

import { jobs as jobsApi } from '../../api'
import type { ApplicationSeeker, Invitation } from '../../api'
import { Alert, ApiActionButton, ApplicationStatusBadge, AsyncPage, Badge, Container, EmptyState, Icon, InvitationStatusBadge, LinkButton, PageHeader, PageStack, Pagination, SectionCard, Textarea } from '../../design-system'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'
import styles from './MyApplicationsPage.module.css'

const PAGE_SIZE = 20

/** /jobs/my-applications — every application the seeker ever made, paginated from the URL (`?page=`). */
export function MyApplicationsPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const goTo = (next: number) => setParams(next > 1 ? { page: String(next) } : {})
  return (
    <Container width="xl">
      <PageHeader eyebrow={<><Icon name="briefcase" size={16} />{t('nav.jobs')}</>} title={t('applications.title')} description={t('applications.intro')} />
      <PageStack>
        <InvitationsBlock />
        <AsyncPage load={(signal) => jobsApi.listMyApplications(page, signal)} deps={[page]}>
          {(result, reload) =>
            result.results.length === 0 ? (
              <div className="card-block">
                {page > 1 ? (
                  <EmptyState icon="briefcase" title={t('applications.emptyPage')} testId="applications-empty-page" action={<LinkButton to="/jobs/my-applications">{t('common.previous')}</LinkButton>} />
                ) : (
                  <EmptyState icon="briefcase" title={t('applications.empty')} testId="applications-empty" action={<LinkButton to="/jobs">{t('applications.browse')}</LinkButton>} />
                )}
              </div>
            ) : (
              <>
                <p className="text-caption" data-testid="applications-count">
                  {t('applications.count', { count: result.count })}
                </p>
                {result.results.map((application) => (
                  <ApplicationCard key={application.id} application={application} reload={reload} />
                ))}
                <Pagination page={page} total={Math.max(1, Math.ceil(result.count / PAGE_SIZE))} hasNext={result.next !== null} hasPrevious={result.previous !== null} onChange={goTo} />
              </>
            )
          }
        </AsyncPage>
      </PageStack>
    </Container>
  )
}

function ApplicationCard({ application, reload }: { application: ApplicationSeeker; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  const canWithdraw = ['SUBMITTED', 'REVIEWING', 'SHORTLISTED'].includes(application.status)
  return (
    <SectionCard
      title={
        <Link to={`/jobs/${application.job.id}`} className={styles.jobLink}>
          {application.job.title}
        </Link>
      }
      description={`${application.job.employer.name} · ${t('applications.appliedOn')} ${new Date(application.submitted_at).toLocaleDateString(i18n.language)}`}
      headingLevel={2}
      actions={<ApplicationStatusBadge status={application.status} />}
      data-testid="application-card"
    >
      {error ? <Alert kind="error">{error}</Alert> : null}
      <div className={styles.columns}>
        <div>
          <h4 className={styles.subtitle}>{t('applications.history')}</h4>
          <ol className={styles.history}>
            {application.transitions.map((tr, i) => (
              <li key={i}>
                <span>{t(`applicationStatus.${tr.to_status}`)}</span>
                <span className="text-caption">{new Date(tr.created_at).toLocaleString(i18n.language)}</span>
                {tr.reason ? <span className="text-caption">{tr.reason}</span> : null}
              </li>
            ))}
          </ol>
          {application.interviews.length > 0 ? (
            <>
              <h4 className={styles.subtitle}>{t('applications.interviews')}</h4>
              <ul className={styles.history}>
                {application.interviews.map((iv) => (
                  <li key={iv.id} data-testid="interview-row">
                    <span>
                      {t('applications.interviewAt')}: {new Date(iv.proposed_at).toLocaleString(i18n.language)} · {t(`applications.interviewModes.${iv.mode}`)}
                    </span>
                    {iv.location_text ? <span className="text-caption">{iv.location_text}</span> : null}
                    {iv.employer_note ? <span className="text-caption">{iv.employer_note}</span> : null}
                    <span>
                      <Badge tone={iv.status === 'ACCEPTED' ? 'success' : iv.status === 'PROPOSED' ? 'warning' : 'neutral'}>{t(`applications.interviewStatus.${iv.status}`)}</Badge>
                    </span>
                    {iv.status === 'PROPOSED' ? (
                      <span className="cluster">
                        <ApiActionButton size="sm" action={() => jobsApi.respondToInterview(iv.id, true)} onSuccess={reload} onError={(e) => setError(toErrorMessage(e))}>
                          {t('applications.accept')}
                        </ApiActionButton>
                        <ApiActionButton size="sm" variant="ghost" action={() => jobsApi.respondToInterview(iv.id, false)} onSuccess={reload} onError={(e) => setError(toErrorMessage(e))}>
                          {t('applications.decline')}
                        </ApiActionButton>
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {canWithdraw ? (
            <div style={{ marginBlockStart: 'var(--space-4)' }}>
              <ApiActionButton variant="ghost" size="sm" action={() => jobsApi.withdrawApplication(application.id)} onSuccess={reload} onError={(e) => setError(toErrorMessage(e))} pendingLabel={t('applications.withdrawing')}>
                {t('applications.withdraw')}
              </ApiActionButton>
            </div>
          ) : null}
        </div>
        <MessagesThread applicationId={application.id} mySide="CANDIDATE" closed={application.status === 'WITHDRAWN' || application.status === 'REJECTED'} />
      </div>
    </SectionCard>
  )
}

/** Text-only recruitment thread scoped to one application (shared by both sides). */
export function MessagesThread({ applicationId, mySide, closed }: { applicationId: string; mySide: 'CANDIDATE' | 'EMPLOYER'; closed: boolean }) {
  const { t, i18n } = useTranslation()
  const messages = useAsyncData((signal) => jobsApi.listMessages(applicationId, signal), [applicationId])
  const [body, setBody] = useState('')
  const [error, setError] = useState<string | null>(null)
  return (
    <div className={styles.thread} data-testid="messages-thread">
      <h4 className={styles.subtitle}>{t('applications.messages')}</h4>
      {messages.loading ? (
        <p className="text-muted">{t('common.loading')}</p>
      ) : messages.error ? (
        <Alert kind="error">{toErrorMessage(messages.error)}</Alert>
      ) : (messages.data ?? []).length === 0 ? (
        <p className="text-muted">{t('applications.noMessages')}</p>
      ) : (
        <ul className={styles.messages}>
          {(messages.data ?? []).map((m) => (
            <li key={m.id} className={m.sender_side === mySide ? styles.mine : styles.theirs}>
              <span className="text-caption">
                {m.sender_side === mySide ? t('applications.me') : mySide === 'CANDIDATE' ? t('applications.employer') : t('talent.candidate')} · {new Date(m.created_at).toLocaleString(i18n.language)}
              </span>
              <p className="prewrap">{m.body}</p>
            </li>
          ))}
        </ul>
      )}
      {!closed ? (
        <form noValidate onSubmit={(e) => e.preventDefault()} className={styles.composer}>
          {error ? <Alert kind="error">{error}</Alert> : null}
          <Textarea label={t('applications.messages')} placeholder={t('applications.messagePlaceholder')} rows={2} value={body} onChange={(e) => setBody(e.target.value)} />
          <ApiActionButton
            type="submit"
            size="sm"
            action={async () => {
              if (!body.trim()) throw new Error(t('validation.required'))
              return jobsApi.sendMessage(applicationId, body.trim())
            }}
            onSuccess={() => {
              setBody('')
              setError(null)
              messages.reload()
            }}
            onError={(e) => setError(toErrorMessage(e))}
            pendingLabel={t('common.sending')}
            leading={<Icon name="mail" size={16} />}
          >
            {t('applications.send')}
          </ApiActionButton>
        </form>
      ) : null}
    </div>
  )
}

function InvitationsBlock() {
  const { t } = useTranslation()
  const invitations = useAsyncData((signal) => jobsApi.listMyInvitations(signal), [])
  const [error, setError] = useState<string | null>(null)
  const pending = (invitations.data?.results ?? []).filter((i) => i.status === 'PENDING')
  if (invitations.loading || invitations.error || (invitations.data?.results ?? []).length === 0) return null
  return (
    <SectionCard title={t('applications.invitations')} headingLevel={2}>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <ul className={styles.history}>
        {(invitations.data?.results ?? []).map((inv: Invitation) => (
          <li key={inv.id} data-testid="invitation-row">
            <span>
              {t('applications.invitedTo')} <Link to={`/jobs/${inv.job.id}`}>{inv.job.title}</Link> · {inv.job.employer.name}
            </span>
            {inv.message ? <span className="text-caption prewrap">{inv.message}</span> : null}
            <span>
              <InvitationStatusBadge status={inv.status} />
            </span>
            {inv.status === 'PENDING' ? (
              <span className="cluster">
                <ApiActionButton size="sm" action={() => jobsApi.respondToInvitation(inv.id, true)} onSuccess={() => invitations.reload()} onError={(e) => setError(toErrorMessage(e))}>
                  {t('applications.acceptInvite')}
                </ApiActionButton>
                <ApiActionButton size="sm" variant="ghost" action={() => jobsApi.respondToInvitation(inv.id, false)} onSuccess={() => invitations.reload()} onError={(e) => setError(toErrorMessage(e))}>
                  {t('applications.declineInvite')}
                </ApiActionButton>
              </span>
            ) : null}
          </li>
        ))}
      </ul>
      {pending.length === 0 ? null : <p className="text-caption">{t('applications.inviteAccepted')}</p>}
    </SectionCard>
  )
}
