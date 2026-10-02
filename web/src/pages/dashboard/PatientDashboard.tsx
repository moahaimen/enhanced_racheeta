import { useTranslation } from 'react-i18next'

import { dashboards as dashboardsApi } from '../../api'
import { AsyncPage, LinkButton, SectionCard } from '../../design-system'
import styles from './Dashboard.module.css'
import { CountGrid, Metric, ReservationRows, UnreadBlock } from './widgets'

export function PatientDashboard() {
  const { t, i18n } = useTranslation()
  return (
    <AsyncPage load={(signal) => dashboardsApi.getPatient(signal)}>
      {(data) => (
        <div className={styles.panel} data-testid="dashboard-patient">
          <SectionCard
            title={t('dashboard.patient.reservations')}
            headingLevel={2}
            actions={
              <LinkButton to="/reservations" variant="ghost" size="sm">
                {t('dashboard.viewAll')}
              </LinkButton>
            }
          >
            <div className="grid-2">
              <Metric
                label={t('dashboard.total')}
                value={data.reservations.total.toLocaleString(i18n.language)}
                testId="reservations-total"
              />
              <Metric
                label={t('dashboard.upcoming')}
                value={data.reservations.upcoming.toLocaleString(i18n.language)}
                hint={t('dashboard.upcomingHint')}
                testId="reservations-upcoming"
              />
            </div>
            <CountGrid counts={data.reservations.by_status} labelGroup="reservationStatus" testPrefix="reservation" />
          </SectionCard>

          <SectionCard title={t('dashboard.patient.upcomingList')} headingLevel={2}>
            <ReservationRows rows={data.upcoming} testId="upcoming-list" />
          </SectionCard>

          <SectionCard title={t('dashboard.patient.recentList')} headingLevel={2}>
            <ReservationRows rows={data.recent} testId="recent-list" />
          </SectionCard>

          <SectionCard title={t('dashboard.unread')} headingLevel={2}>
            <UnreadBlock {...data.unread} />
          </SectionCard>
        </div>
      )}
    </AsyncPage>
  )
}
