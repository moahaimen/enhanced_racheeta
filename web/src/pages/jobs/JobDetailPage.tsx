import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'

import { ApiError, jobs as jobsApi } from '../../api'
import type { JobPublic } from '../../api'
import { useAuth } from '../../auth/useAuth'
import { Alert, ApiActionButton, AsyncPage, Badge, Container, formatSalary, Icon, LinkButton, PageStack, SectionCard, Textarea, useFormErrors } from '../../design-system'
import { useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import styles from './JobDetailPage.module.css'

/** Public job page. Real data only; no contact channels; application stays inside Racheeta. */
export function JobDetailPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const load = async (signal: AbortSignal) => {
    try {
      return await jobsApi.getJob(id, signal)
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) throw new ApiError(404, 'not_found', t('jobDetail.notFound'))
      throw error
    }
  }
  return (
    <Container width="xl">
      <AsyncPage load={load} deps={[id]}>
        {(job) => <JobDetail job={job} />}
      </AsyncPage>
    </Container>
  )
}

function JobDetail({ job }: { job: JobPublic }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const salary = job.salary_visible ? formatSalary(job, i18n.language) : null
  const hiringName = job.hiring_employer?.name || job.hiring_organization_name
  return (
    <PageStack>
      <section className={styles.hero} aria-labelledby="job-title">
        <h1 id="job-title">{job.title}</h1>
        <div className={styles.employer}>
          <Icon name="building" size={18} />
          <Link to={`/employers/${job.employer.id}`}>{job.employer.name}</Link>
          {job.employer.is_verified ? (
            <Badge tone="success" leading={<Icon name="shieldCheck" size={12} />}>
              {t('jobs.verifiedEmployer')}
            </Badge>
          ) : null}
          {job.employer.is_recruitment_agency ? <Badge tone="outline">{hiringName ? t('jobs.agencyFor', { name: hiringName }) : t('jobs.agencyListing')}</Badge> : null}
        </div>
        <div className={styles.meta}>
          <Badge tone="brand">{t(`professions.${job.profession}`)}</Badge>
          {job.general_specialty ? <Badge tone="outline">{name(job.general_specialty)}</Badge> : null}
          <Badge tone="outline">{t(`employmentTypes.${job.employment_type}`)}</Badge>
          <Badge tone="outline">{t(`workModes.${job.work_mode}`)}</Badge>
          {job.shift_type ? <Badge tone="outline">{t(`shiftTypes.${job.shift_type}`)}</Badge> : null}
          {job.is_featured ? <Badge tone="brand" leading={<Icon name="sparkle" size={12} />}>{t('jobs.featured')}</Badge> : null}
        </div>
        <p className="text-muted" style={{ marginBlockStart: 'var(--space-3)' }}>
          <Icon name="mapPin" size={14} /> {name(job.governorate)}
          {job.city ? ` — ${name(job.city)}` : ''}
          {job.published_at ? ` · ${new Date(job.published_at).toLocaleDateString(i18n.language)}` : ''}
        </p>
        <p style={{ marginBlockStart: 'var(--space-3)' }}>
          <Link to="/jobs">
            <Icon name="chevronBack" size={14} flipInRtl /> {t('jobDetail.back')}
          </Link>
        </p>
      </section>

      <div className={styles.layout}>
        <PageStack>
          <SectionCard title={t('jobDetail.summary')} headingLevel={2}>
            <p className="prewrap">{job.description}</p>
          </SectionCard>
          {job.responsibilities ? (
            <SectionCard title={t('jobDetail.responsibilities')} headingLevel={2}>
              <p className="prewrap">{job.responsibilities}</p>
            </SectionCard>
          ) : null}
          {job.requirements ? (
            <SectionCard title={t('jobDetail.requirements')} headingLevel={2}>
              <p className="prewrap">{job.requirements}</p>
            </SectionCard>
          ) : null}
          <SectionCard title={t('jobDetail.experience')} headingLevel={2}>
            <dl className={styles.facts}>
              <dt>{t('jobDetail.minDegree')}</dt>
              <dd>{job.minimum_degree ? t(`degrees.${job.minimum_degree}`) : t('common.unspecified')}</dd>
              <dt>{t('jobDetail.minExperience')}</dt>
              <dd>{t('talent.experienceYears', { count: job.minimum_experience_years })}</dd>
            </dl>
          </SectionCard>
        </PageStack>
        <PageStack>
          <div className={styles.sticky}>
            <PageStack>
              <ApplyBlock job={job} />
              <SectionCard title={t('jobDetail.location')} headingLevel={2}>
                <dl className={styles.facts}>
                  <dt>{t('jobsPage.filters.governorate')}</dt>
                  <dd>
                    {name(job.governorate)}
                    {job.city ? ` — ${name(job.city)}` : ''}
                  </dd>
                  {job.workplace_text ? (
                    <>
                      <dt>{t('jobDetail.workplace')}</dt>
                      <dd>{job.workplace_text}</dd>
                    </>
                  ) : null}
                  <dt>{t('jobsPage.filters.work_mode')}</dt>
                  <dd>{t(`workModes.${job.work_mode}`)}</dd>
                  <dt>{t('jobDetail.openings')}</dt>
                  <dd>{job.number_of_openings}</dd>
                  {job.application_deadline ? (
                    <>
                      <dt>{t('jobDetail.deadline')}</dt>
                      <dd>{new Date(job.application_deadline).toLocaleDateString(i18n.language)}</dd>
                    </>
                  ) : null}
                </dl>
              </SectionCard>
              <SectionCard title={t('jobDetail.salary')} headingLevel={2}>
                {salary ? <p className={styles.salary}>{salary}</p> : <p className="text-muted">{t('jobDetail.salaryHidden')}</p>}
              </SectionCard>
              <SectionCard title={t('jobDetail.employer')} headingLevel={2}>
                <p>
                  <strong>{job.employer.name}</strong> · {t(`organizationTypes.${job.employer.organization_type}`)}
                </p>
                {job.employer.description ? <p className="text-secondary prewrap">{job.employer.description}</p> : null}
                <p className="text-caption" style={{ marginBlockStart: 'var(--space-2)' }}>
                  {t('jobDetail.noContact')}
                </p>
              </SectionCard>
            </PageStack>
          </div>
        </PageStack>
      </div>
    </PageStack>
  )
}

function ApplyBlock({ job }: { job: JobPublic }) {
  const { t } = useTranslation()
  const { status, account } = useAuth()
  const [cover, setCover] = useState('')
  const [applied, setApplied] = useState(false)
  const errors = useFormErrors(['cover_text'] as const)
  const profile = useAsyncData(
    (signal) => (status === 'authenticated' ? jobsApi.getMySeekerProfile(signal).catch((e: unknown) => (e instanceof ApiError && e.status === 404 ? null : Promise.reject(e))) : Promise.resolve(null)),
    [status],
  )

  if (!job.is_open) {
    return (
      <SectionCard title={t('jobDetail.apply')} headingLevel={2}>
        <Alert kind="info">{t('jobDetail.closed')}</Alert>
      </SectionCard>
    )
  }
  if (status === 'anonymous') {
    return (
      <SectionCard title={t('jobDetail.apply')} headingLevel={2}>
        <LinkButton to="/login" block>
          {t('jobDetail.loginToApply')}
        </LinkButton>
      </SectionCard>
    )
  }
  if (status !== 'authenticated' || profile.loading) {
    return (
      <SectionCard title={t('jobDetail.apply')} headingLevel={2}>
        <div className="cluster">
          <span className="text-muted">{t('common.loading')}</span>
        </div>
      </SectionCard>
    )
  }
  if (account?.role === 'MEDICAL_COMPANY' || account?.role === 'REAL_ESTATE_SELLER') {
    return (
      <SectionCard title={t('jobDetail.apply')} headingLevel={2}>
        <p className="text-muted">{t('jobDetail.employerCannotApply')}</p>
      </SectionCard>
    )
  }
  if (!profile.data) {
    return (
      <SectionCard title={t('jobDetail.apply')} headingLevel={2}>
        <LinkButton to="/jobs/profile" block variant="secondary">
          {t('jobDetail.createProfileToApply')}
        </LinkButton>
      </SectionCard>
    )
  }
  if (applied) {
    return (
      <SectionCard title={t('jobDetail.apply')} headingLevel={2}>
        <Alert kind="success">{t('jobDetail.applied')}</Alert>
        <LinkButton to="/jobs/my-applications" variant="secondary" block>
          {t('nav.myApplications')}
        </LinkButton>
      </SectionCard>
    )
  }
  return (
    <SectionCard title={t('jobDetail.apply')} headingLevel={2}>
      <form noValidate onSubmit={(e) => e.preventDefault()}>
        {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
        <Textarea label={t('jobDetail.coverText')} hint={t('jobDetail.coverHint')} rows={3} value={cover} onChange={(e) => setCover(e.target.value)} error={errors.fieldErrors.cover_text} />
        <ApiActionButton type="submit" block action={() => jobsApi.applyToJob(job.id, cover.trim())} onSuccess={() => setApplied(true)} onError={(error) => errors.applyApiError(error)} pendingLabel={t('jobDetail.applying')} leading={<Icon name="check" size={18} />}>
          {t('jobDetail.apply')}
        </ApiActionButton>
      </form>
    </SectionCard>
  )
}
