import { useTranslation } from 'react-i18next'

import { dashboards as dashboardsApi } from '../../api'
import { Alert, AsyncPage, Badge, SectionCard } from '../../design-system'
import styles from './Dashboard.module.css'
import { CountGrid, Metric, WorkspaceLinks } from './widgets'

export function RecruiterDashboardView() {
  const { t, i18n } = useTranslation()
  const n = (value: number) => value.toLocaleString(i18n.language)
  return (
    <AsyncPage load={(signal) => dashboardsApi.getRecruiter(signal)}>
      {(data) => (
        <div className={styles.panel} data-testid="dashboard-recruiter">
          <SectionCard
            title={data.organization.name}
            headingLevel={2}
            description={`${t('employer.myRole')}: ${t(`employer.roles.${data.organization.my_role}`, { defaultValue: data.organization.my_role })}`}
            actions={
              <Badge tone={data.organization.can_recruit ? 'success' : 'warning'}>
                {t(`verification.${data.organization.verification_status}`)}
              </Badge>
            }
          >
            {!data.organization.can_recruit ? (
              <Alert kind="warning">{t('dashboard.recruiter.cannotRecruit')}</Alert>
            ) : null}
            <WorkspaceLinks links={[{ to: '/employer', label: t('nav.employer') }]} />
          </SectionCard>

          <SectionCard title={t('dashboard.recruiter.jobs')} headingLevel={2}>
            <div className="grid-2">
              <Metric label={t('dashboard.total')} value={n(data.jobs.total)} testId="jobs-total" />
              <Metric
                label={t('dashboard.recruiter.openNow')}
                value={n(data.jobs.open_now)}
                hint={t('dashboard.recruiter.openNowHint')}
                testId="jobs-open"
              />
            </div>
            <CountGrid counts={data.jobs.by_status} labelGroup="jobStatus" testPrefix="job" />
          </SectionCard>

          <SectionCard title={t('dashboard.recruiter.applications')} headingLevel={2}>
            {data.applications === null ? (
              <Alert kind="info">
                <span data-testid="applications-withheld">
                  {t(`dashboard.recruiter.access.${data.applications_access ?? 'plan_required'}`)}
                </span>
              </Alert>
            ) : (
              <>
                <div className="grid-2">
                  <Metric label={t('dashboard.total')} value={n(data.applications.total)} testId="applications-total" />
                  <Metric
                    label={t('dashboard.recruiter.awaitingReview')}
                    value={n(data.applications.awaiting_review)}
                    hint={t('dashboard.recruiter.awaitingReviewHint')}
                    testId="applications-awaiting"
                  />
                  <Metric
                    label={t('dashboard.recruiter.last7Days')}
                    value={n(data.applications.last_7_days)}
                    testId="applications-recent"
                  />
                </div>
                <CountGrid counts={data.applications.by_status} labelGroup="applicationStatus" testPrefix="application" />
              </>
            )}
          </SectionCard>

          {data.interviews ? (
            <SectionCard title={t('dashboard.recruiter.interviews')} headingLevel={2}>
              <CountGrid counts={data.interviews.by_status} labelGroup="dashboard.interviewStatus" testPrefix="interview" />
            </SectionCard>
          ) : null}

          <SectionCard title={t('dashboard.recruiter.seats')} headingLevel={2}>
            <div className="grid-2">
              <Metric label={t('dashboard.recruiter.activeMembers')} value={n(data.seats.active_members)} testId="seats-active" />
              <Metric
                label={t('dashboard.recruiter.seatLimit')}
                value={data.seats.limit === null ? t('common.unlimited') : n(data.seats.limit)}
                testId="seats-limit"
              />
            </div>
          </SectionCard>
        </div>
      )}
    </AsyncPage>
  )
}
