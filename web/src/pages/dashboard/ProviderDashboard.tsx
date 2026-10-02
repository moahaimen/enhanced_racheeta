import { useTranslation } from 'react-i18next'

import { dashboards as dashboardsApi } from '../../api'
import type { DoctorDashboard, FacilityDashboard } from '../../api'
import { AsyncPage, Badge, SectionCard } from '../../design-system'
import styles from './Dashboard.module.css'
import { CountGrid, Metric, ReservationRows, UnreadBlock, WorkspaceLinks } from './widgets'

function ProviderView({ data, facility }: { data: DoctorDashboard | FacilityDashboard; facility?: FacilityDashboard['practitioners'] }) {
  const { t, i18n } = useTranslation()
  const n = (value: number) => value.toLocaleString(i18n.language)
  const { profile, reviews, offers } = data
  return (
    <div className={styles.panel} data-testid={facility ? 'dashboard-facility' : 'dashboard-doctor'}>
      <SectionCard
        title={profile.display_name}
        headingLevel={2}
        description={t(`providerTypes.${profile.provider_type}`)}
        actions={
          <Badge tone={profile.verification_status === 'VERIFIED' ? 'success' : 'warning'}>
            {t(`verification.${profile.verification_status}`)}
          </Badge>
        }
      >
        {profile.verification_status !== 'VERIFIED' || !profile.is_visible ? (
          <p className="text-caption" data-testid="provider-not-discoverable">
            {t('dashboard.provider.notDiscoverable')}
          </p>
        ) : null}
        <WorkspaceLinks
          links={[
            { to: '/provider/reservations', label: t('nav.providerReservations') },
            { to: '/provider/offers', label: t('nav.providerOffers') },
            { to: '/provider/profile', label: t('nav.providerProfile') },
          ]}
        />
      </SectionCard>

      <SectionCard title={t('dashboard.provider.reservations')} headingLevel={2}>
        <div className="grid-2">
          <Metric label={t('dashboard.total')} value={n(data.reservations.total)} testId="reservations-total" />
          <Metric
            label={t('dashboard.upcoming')}
            value={n(data.reservations.upcoming)}
            hint={t('dashboard.upcomingHint')}
            testId="reservations-upcoming"
          />
        </div>
        <CountGrid counts={data.reservations.by_status} labelGroup="reservationStatus" testPrefix="reservation" />
      </SectionCard>

      <SectionCard title={t('dashboard.provider.upcomingList')} headingLevel={2}>
        <ReservationRows rows={data.upcoming} patientName testId="upcoming-list" />
      </SectionCard>

      <SectionCard title={t('dashboard.provider.reviews')} headingLevel={2}>
        {reviews.review_count === 0 ? (
          <p data-testid="no-reviews">{t('dashboard.provider.noReviews')}</p>
        ) : (
          <div className="grid-2">
            <Metric
              label={t('dashboard.provider.averageRating')}
              value={(reviews.average_rating ?? 0).toLocaleString(i18n.language, { maximumFractionDigits: 2 })}
              testId="rating-average"
            />
            <Metric label={t('dashboard.provider.reviewCount')} value={n(reviews.review_count)} testId="rating-count" />
          </div>
        )}
        <CountGrid counts={reviews.distribution} labelGroup="dashboard.stars" testPrefix="stars" />
      </SectionCard>

      <SectionCard title={t('dashboard.provider.offers')} headingLevel={2}>
        <div className="grid-2">
          <Metric label={t('dashboard.provider.offersRunning')} value={n(offers.running_now)} testId="offers-running" />
          <Metric label={t('dashboard.provider.offersScheduled')} value={n(offers.scheduled)} testId="offers-scheduled" />
        </div>
      </SectionCard>

      {facility ? (
        <SectionCard title={t('dashboard.facility.practitioners')} headingLevel={2}>
          <div className={styles.countGrid}>
            <Metric label={t('dashboard.facility.active')} value={n(facility.active)} testId="members-active" />
            <Metric
              label={t('dashboard.facility.incoming')}
              value={n(facility.incoming_requests)}
              hint={t('dashboard.facility.incomingHint')}
              testId="members-incoming"
            />
            <Metric
              label={t('dashboard.facility.outgoing')}
              value={n(facility.outgoing_invitations)}
              hint={t('dashboard.facility.outgoingHint')}
              testId="members-outgoing"
            />
          </div>
        </SectionCard>
      ) : null}

      <SectionCard title={t('dashboard.unread')} headingLevel={2}>
        <UnreadBlock {...data.unread} />
      </SectionCard>
    </div>
  )
}

export function DoctorDashboard() {
  return <AsyncPage load={(signal) => dashboardsApi.getDoctor(signal)}>{(data) => <ProviderView data={data} />}</AsyncPage>
}

export function FacilityDashboardView() {
  return (
    <AsyncPage load={(signal) => dashboardsApi.getFacility(signal)}>
      {(data) => <ProviderView data={data} facility={data.practitioners} />}
    </AsyncPage>
  )
}
