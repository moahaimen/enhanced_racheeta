import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router'

import { ApiError, jobs as jobsApi } from '../../api'
import type { EmployerPublic } from '../../api'
import { AsyncPage, Badge, Container, EmptyState, Icon, JobCard, JobCardSkeleton, LinkButton, PageHeader, PageStack, Pagination, SectionCard } from '../../design-system'
import { useLocalizedName } from '../../i18n/localized'
import styles from './JobsPage.module.css'

const PAGE_SIZE = 20

/** /employers/:id — public organisation page: description and its published jobs, paginated (`?jobs_page=`). No contact data. */
export function EmployerPublicPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const name = useLocalizedName()
  const load = async (signal: AbortSignal) => {
    try {
      return await jobsApi.getEmployerPublic(id, signal)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) throw new ApiError(404, 'not_found', t('jobDetail.notFound'))
      throw e
    }
  }
  return (
    <Container width="xl">
      <AsyncPage load={load} deps={[id]}>
        {(employer) => (
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
              <EmployerJobs employer={employer} />
            </PageStack>
          </>
        )}
      </AsyncPage>
    </Container>
  )
}

/** The employer's published jobs; the header above stays mounted while a page loads. */
function EmployerJobs({ employer }: { employer: EmployerPublic }) {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('jobs_page') ?? '1') || 1)
  const goTo = (next: number) =>
    setParams((prev) => {
      const out = new URLSearchParams(prev)
      if (next > 1) out.set('jobs_page', String(next))
      else out.delete('jobs_page')
      return out
    })
  return (
    <SectionCard title={t('jobsPage.title')} headingLevel={2}>
      <AsyncPage
        load={(signal) => jobsApi.listJobs({ employer: employer.id, page, page_size: PAGE_SIZE }, signal)}
        deps={[employer.id, page]}
        skeleton={
          <ul className={styles.grid} data-testid="employer-jobs-loading" aria-busy="true">
            {Array.from({ length: 3 }, (_, i) => (
              <li key={i}>
                <JobCardSkeleton />
              </li>
            ))}
          </ul>
        }
      >
        {(jobs) => (
          <>
            {jobs.results.length === 0 ? (
              page > 1 ? (
                <EmptyState icon="briefcase" title={t('jobsPage.emptyPage')} testId="employer-jobs-empty-page" action={<LinkButton to={`/employers/${employer.id}`} variant="ghost">{t('common.previous')}</LinkButton>} />
              ) : (
                <EmptyState icon="briefcase" title={t('jobsPage.empty')} testId="employer-jobs-empty" />
              )
            ) : (
              <>
                <p className="text-caption" data-testid="employer-jobs-count">
                  {t('jobsPage.results', { count: jobs.count })}
                </p>
                <ul className={styles.grid} aria-label={t('jobsPage.title')}>
                  {jobs.results.map((job) => (
                    <li key={job.id}>
                      <JobCard job={job} />
                    </li>
                  ))}
                </ul>
              </>
            )}
            <Pagination page={page} total={Math.max(1, Math.ceil(jobs.count / PAGE_SIZE))} hasNext={jobs.next !== null} hasPrevious={jobs.previous !== null} onChange={goTo} />
          </>
        )}
      </AsyncPage>
    </SectionCard>
  )
}
