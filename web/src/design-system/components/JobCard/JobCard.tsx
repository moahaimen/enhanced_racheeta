import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import type { JobCard as JobCardData } from '../../../api'
import { useLocalizedName } from '../../../i18n/localized'
import { Icon } from '../../icons'
import { Badge } from '../Badge/Badge'
import { Card } from '../Card/Card'
import { Skeleton } from '../States/States'
import { formatSalary } from './formatSalary'
import styles from './JobCard.module.css'


/** Signature job card. Only real API fields; no views/applicant counts/ratings. */
export function JobCard({ job }: { job: JobCardData }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const salary = job.salary_visible ? formatSalary(job, i18n.language) : null
  const hiringName = job.hiring_employer?.name || job.hiring_organization_name
  return (
    <Card as="article" interactive className={`${styles.card} ${job.is_featured ? styles.featured : ''}`.trim()}>
      <div className={styles.head}>
        <h3 className={styles.title}>
          <Link to={`/jobs/${job.id}`}>{job.title}</Link>
        </h3>
        {job.is_featured ? <Badge tone="brand" leading={<Icon name="sparkle" size={12} />}>{t('jobs.featured')}</Badge> : null}
      </div>
      <div className={styles.employer}>
        <Icon name="building" size={16} />
        <span>{job.employer.name}</span>
        {job.employer.is_verified ? (
          <Badge tone="success" leading={<Icon name="shieldCheck" size={12} />}>
            {t('jobs.verifiedEmployer')}
          </Badge>
        ) : null}
      </div>
      {job.employer.is_recruitment_agency ? (
        <div className={styles.agency}>
          {hiringName ? t('jobs.agencyFor', { name: hiringName }) : t('jobs.agencyListing')}
        </div>
      ) : null}
      <div className={styles.meta}>
        <Badge tone="outline">{t(`professions.${job.profession}`)}</Badge>
        {job.general_specialty ? <Badge tone="outline">{name(job.general_specialty)}</Badge> : null}
        <Badge tone="outline">{t(`employmentTypes.${job.employment_type}`)}</Badge>
      </div>
      <div className={styles.facts}>
        <span>
          <Icon name="mapPin" size={14} />
          {name(job.governorate)}
          {job.city ? ` — ${name(job.city)}` : ''}
        </span>
        {job.published_at ? (
          <span>
            <Icon name="calendar" size={14} />
            {new Date(job.published_at).toLocaleDateString(i18n.language)}
          </span>
        ) : null}
        {job.application_deadline ? (
          <span>
            <Icon name="clock" size={14} />
            {t('jobs.deadline')}: {new Date(job.application_deadline).toLocaleDateString(i18n.language)}
          </span>
        ) : null}
      </div>
      <div className={styles.footer}>
        <span className={styles.salary}>{salary ?? ''}</span>
        <span aria-hidden="true">
          {t('jobs.viewJob')} <Icon name="arrowForward" size={16} flipInRtl />
        </span>
      </div>
    </Card>
  )
}

export function JobCardSkeleton() {
  return (
    <Card className={styles.card} aria-hidden="true">
      <Skeleton width="75%" height="1.2rem" />
      <Skeleton width="45%" height="0.9rem" />
      <Skeleton width="90%" height="1.4rem" />
      <Skeleton width="60%" height="0.9rem" />
    </Card>
  )
}
