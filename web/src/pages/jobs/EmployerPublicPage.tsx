import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'

import { ApiError, jobs as jobsApi } from '../../api'
import { AsyncPage, Badge, Container, EmptyState, Icon, JobCard, PageHeader, PageStack, SectionCard } from '../../design-system'
import { useLocalizedName } from '../../i18n/localized'
import styles from './JobsPage.module.css'

/** /employers/:id — public organisation page: description and its published jobs. No contact data. */
export function EmployerPublicPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const name = useLocalizedName()
  const load = async (signal: AbortSignal) => {
    try {
      return await Promise.all([jobsApi.getEmployerPublic(id, signal), jobsApi.listJobs({ employer: id, page_size: 20 }, signal)])
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) throw new ApiError(404, 'not_found', t('jobDetail.notFound'))
      throw e
    }
  }
  return (
    <Container width="xl">
      <AsyncPage load={load} deps={[id]}>
        {([employer, jobs]) => (
          <>
            <PageHeader
              eyebrow={
                <Link to="/jobs" className="cluster">
                  <Icon name="chevronBack" size={14} flipInRtl /> {t('nav.jobs')}
                </Link>
              }
              title={employer.name}
              description={`${t(`organizationTypes.${employer.organization_type}`)} · ${name(employer.governorate)}${employer.city ? ` — ${name(employer.city)}` : ''}`}
              actions={
                <span className="cluster">
                  {employer.is_verified ? (
                    <Badge tone="success">
                      <Icon name="shieldCheck" size={14} /> {t('jobs.verifiedEmployer')}
                    </Badge>
                  ) : null}
                  {employer.is_recruitment_agency ? <Badge tone="outline">{t('organizationTypes.RECRUITMENT_AGENCY')}</Badge> : null}
                </span>
              }
            />
            <PageStack>
              {employer.description ? (
                <SectionCard title={t('employer.description')} headingLevel={2}>
                  <p className="prewrap">{employer.description}</p>
                </SectionCard>
              ) : null}
              {employer.provider_profile_id ? (
                <p>
                  <Link to={`/providers/${employer.provider_profile_id}`}>{t('jobDetail.providerProfile')}</Link>
                </p>
              ) : null}
              <SectionCard title={t('jobsPage.title')} headingLevel={2}>
                {jobs.results.length === 0 ? (
                  <EmptyState icon="briefcase" title={t('jobsPage.empty')} testId="employer-jobs-empty" />
                ) : (
                  <ul className={styles.grid} aria-label={t('jobsPage.title')}>
                    {jobs.results.map((job) => (
                      <li key={job.id}>
                        <JobCard job={job} />
                      </li>
                    ))}
                  </ul>
                )}
              </SectionCard>
            </PageStack>
          </>
        )}
      </AsyncPage>
    </Container>
  )
}
