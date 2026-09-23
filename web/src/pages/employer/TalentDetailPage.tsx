import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'

import { ApiError, jobs as jobsApi } from '../../api'
import type { JobEmployer, TalentDetail } from '../../api'
import { Alert, ApiActionButton, AsyncPage, Badge, Container, FormActions, Icon, PageHeader, PageStack, SectionCard, Select, Textarea, TextField, useFormErrors } from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { ClientValidationError } from '../validation'
import styles from './EmployerWorkspacePage.module.css'

/** /employer/talent/:id — professional profile (no contact data), save and invite actions. */
export function TalentDetailPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const load = async (signal: AbortSignal) => {
    try {
      const [candidate, jobs] = await Promise.all([jobsApi.getTalent(id, signal), jobsApi.listEmployerJobs('PUBLISHED', 1, signal)])
      return [candidate, jobs.results] as [TalentDetail, JobEmployer[]]
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) throw new ApiError(404, 'not_found', t('talent.notFound'))
      throw e
    }
  }
  return (
    <Container width="xl">
      <AsyncPage load={load} deps={[id]}>
        {([candidate, jobs], reload) => <Detail candidate={candidate} jobs={jobs} reload={reload} />}
      </AsyncPage>
    </Container>
  )
}

function Detail({ candidate: c, jobs, reload }: { candidate: TalentDetail; jobs: JobEmployer[]; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const [saveNote, setSaveNote] = useState('')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [job, setJob] = useState(jobs[0]?.id ?? '')
  const [message, setMessage] = useState('')
  const [invited, setInvited] = useState(false)
  const errors = useFormErrors(['job', 'job_seeker', 'message'] as const)
  return (
    <>
      <PageHeader
        eyebrow={
          <Link to="/employer/talent" className="cluster">
            <Icon name="chevronBack" size={14} flipInRtl /> {t('talent.title')}
          </Link>
        }
        title={c.professional_title}
        description={`${t(`professions.${c.profession}`)} · ${t(`degrees.${c.degree}`)} · ${t('talent.experienceYears', { count: c.years_of_experience })}`}
        actions={
          <div className="cluster">
            {c.general_specialty ? <Badge tone="brand">{name(c.general_specialty)}</Badge> : null}
            <Badge tone="outline">{t(`availabilities.${c.availability}`)}</Badge>
            {c.is_saved ? <Badge tone="success">{t('talent.saved')}</Badge> : null}
          </div>
        }
      />
      <div className={styles.layout} style={{ gridTemplateColumns: undefined }}>
        <PageStack>
          <div className="grid-2">
            <PageStack>
              <SectionCard title={t('talent.summary')} headingLevel={2}>
                <p className="prewrap">{c.professional_summary || t('seekerProfile.noItems')}</p>
                <dl className="text-body-sm" style={{ marginBlockStart: 'var(--space-3)' }}>
                  <dt className="text-muted">{t('seekerProfile.governorate')}</dt>
                  <dd>
                    {name(c.governorate)}
                    {c.city ? ` — ${name(c.city)}` : ''}
                  </dd>
                  {c.desired_governorate ? (
                    <>
                      <dt className="text-muted">{t('seekerProfile.desiredGovernorate')}</dt>
                      <dd>{name(c.desired_governorate)}</dd>
                    </>
                  ) : null}
                  <dt className="text-muted">{t('seekerProfile.employmentPreferences')}</dt>
                  <dd>{c.employment_preferences.map((e) => t(`employmentTypes.${e}`)).join('، ') || t('common.unspecified')}</dd>
                  {c.institution_name ? (
                    <>
                      <dt className="text-muted">{t('seekerProfile.institution')}</dt>
                      <dd>
                        {c.institution_name}
                        {c.graduation_year ? ` (${c.graduation_year})` : ''}
                      </dd>
                    </>
                  ) : null}
                </dl>
              </SectionCard>
              <SectionCard title={t('talent.experiences')} headingLevel={2}>
                {c.experiences.length === 0 ? <p className="text-muted">{t('seekerProfile.noItems')}</p> : null}
                <ul className={styles.list}>
                  {c.experiences.map((x) => (
                    <li key={x.id} className={styles.row}>
                      <div className={styles.rowText}>
                        <div className={styles.rowTitle}>{x.title}</div>
                        <div className="text-caption">
                          {x.organization_name} · {new Date(x.start_date).toLocaleDateString(i18n.language)} – {x.is_current ? t('seekerProfile.current') : x.end_date ? new Date(x.end_date).toLocaleDateString(i18n.language) : ''}
                        </div>
                        {x.description ? <p className="text-secondary prewrap">{x.description}</p> : null}
                      </div>
                    </li>
                  ))}
                </ul>
              </SectionCard>
              <SectionCard title={t('talent.education')} headingLevel={2}>
                {c.education.length === 0 ? <p className="text-muted">{t('seekerProfile.noItems')}</p> : null}
                <ul className={styles.list}>
                  {c.education.map((x) => (
                    <li key={x.id} className={styles.row}>
                      <div className={styles.rowText}>
                        <div className={styles.rowTitle}>{t(`degrees.${x.degree}`)} · {x.field_of_study}</div>
                        <div className="text-caption">{x.institution_name}{x.end_year ? ` · ${x.end_year}` : ''}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            </PageStack>
            <PageStack>
              <SectionCard title={t('talent.skills')} headingLevel={2}>
                <div className="cluster">
                  {c.skills.length === 0 ? <span className="text-muted">{t('seekerProfile.noItems')}</span> : null}
                  {c.skills.map((s) => (
                    <Badge key={s} tone="outline">
                      {s}
                    </Badge>
                  ))}
                </div>
              </SectionCard>
              <SectionCard title={t('talent.languages')} headingLevel={2}>
                <div className="cluster">
                  {c.languages.length === 0 ? <span className="text-muted">{t('seekerProfile.noItems')}</span> : null}
                  {c.languages.map((l) => (
                    <Badge key={l.id} tone="outline">
                      {l.language} · {t(`languageLevels.${l.level}`)}
                    </Badge>
                  ))}
                </div>
              </SectionCard>
              <SectionCard title={t('talent.credentials')} headingLevel={2}>
                {c.credentials.length === 0 ? <p className="text-muted">{t('seekerProfile.noItems')}</p> : null}
                <ul className={styles.list}>
                  {c.credentials.map((x) => (
                    <li key={x.id} className={styles.row}>
                      <div className={styles.rowText}>
                        <div className={styles.rowTitle}>{x.name}</div>
                        <div className="text-caption">{t(`seekerProfile.kinds.${x.kind}`)}{x.issuer ? ` · ${x.issuer}` : ''}{x.year ? ` · ${x.year}` : ''}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </SectionCard>
              <SectionCard title={t('talent.save')} headingLevel={2}>
                {saveError ? <Alert kind="error">{saveError}</Alert> : null}
                {c.is_saved ? (
                  <p className="text-muted">{t('talent.saved')}</p>
                ) : (
                  <form noValidate onSubmit={(e) => e.preventDefault()}>
                    <TextField label={t('talent.savedNote')} optional value={saveNote} onChange={(e) => setSaveNote(e.target.value)} />
                    <FormActions>
                      <ApiActionButton type="submit" variant="secondary" action={() => jobsApi.saveCandidate(c.id, saveNote.trim())} onSuccess={reload} onError={(e) => setSaveError(toErrorMessage(e))} leading={<Icon name="check" size={16} />}>
                        {t('talent.save')}
                      </ApiActionButton>
                    </FormActions>
                  </form>
                )}
              </SectionCard>
              <SectionCard title={t('talent.invite')} headingLevel={2}>
                {invited ? (
                  <Alert kind="success">{t('talent.invited')}</Alert>
                ) : jobs.length === 0 ? (
                  <p className="text-muted">{t('employer.noJobs')}</p>
                ) : (
                  <form noValidate onSubmit={(e) => e.preventDefault()}>
                    {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
                    <Select label={t('talent.inviteJob')} value={job} onChange={(e) => setJob(e.target.value)} error={errors.fieldErrors.job}>
                      {jobs.map((j) => (
                        <option key={j.id} value={j.id}>
                          {j.title}
                        </option>
                      ))}
                    </Select>
                    <Textarea label={t('talent.inviteMessage')} optional rows={2} value={message} onChange={(e) => setMessage(e.target.value)} error={errors.fieldErrors.message} />
                    <FormActions>
                      <ApiActionButton
                        type="submit"
                        action={async () => {
                          if (!job) {
                            errors.setFieldErrors({ job: t('validation.required') })
                            throw new ClientValidationError()
                          }
                          return jobsApi.inviteCandidate(job, c.id, message.trim())
                        }}
                        onSuccess={() => setInvited(true)}
                        onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }}
                        pendingLabel={t('common.sending')}
                        leading={<Icon name="mail" size={16} />}
                      >
                        {t('talent.sendInvite')}
                      </ApiActionButton>
                    </FormActions>
                  </form>
                )}
              </SectionCard>
            </PageStack>
          </div>
        </PageStack>
      </div>
    </>
  )
}
