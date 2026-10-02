import { useTranslation } from 'react-i18next'

import { dashboards as dashboardsApi, realEstate as realEstateApi } from '../../api'
import { AsyncPage, Badge, SectionCard } from '../../design-system'
import styles from './Dashboard.module.css'
import { CountGrid, Metric, WorkspaceLinks } from './widgets'

export function MedicalCompanyDashboardView() {
  const { t, i18n } = useTranslation()
  const n = (value: number) => value.toLocaleString(i18n.language)
  return (
    <AsyncPage load={(signal) => dashboardsApi.getCompany(signal)}>
      {(data) => (
        <div className={styles.panel} data-testid="dashboard-company">
          <SectionCard
            title={t('company.dashboard')}
            headingLevel={2}
            actions={
              <Badge tone={data.verification_status === 'VERIFIED' ? 'success' : 'warning'}>
                {t(`verification.${data.verification_status}`)}
              </Badge>
            }
          >
            <WorkspaceLinks
              links={[
                { to: '/company', label: t('nav.companyWorkspace') },
                { to: '/company/advertising', label: t('nav.advertising') },
              ]}
            />
          </SectionCard>

          <SectionCard title={t('dashboard.company.products')} headingLevel={2}>
            <div className={styles.countGrid}>
              <Metric label={t('company.productsTotal')} value={n(data.products.total)} testId="products-total" />
              <Metric label={t('company.productsActive')} value={n(data.products.active)} testId="products-active" />
              <Metric label={t('company.productsInactive')} value={n(data.products.inactive)} testId="products-inactive" />
              <Metric
                label={t('company.productsExposable')}
                value={n(data.products.exposable)}
                hint={t('company.exposableHint')}
                testId="products-exposable"
              />
            </div>
          </SectionCard>

          <SectionCard title={t('dashboard.company.campaigns')} headingLevel={2} description={t('dashboard.company.noAnalytics')}>
            <div className={styles.countGrid}>
              <Metric label={t('advertising.stats.total')} value={n(data.campaigns.total)} testId="campaigns-total" />
              <Metric label={t('advertising.stats.draft')} value={n(data.campaigns.draft)} testId="campaigns-draft" />
              <Metric label={t('advertising.stats.pending')} value={n(data.campaigns.pending_payment)} testId="campaigns-pending" />
              <Metric label={t('advertising.stats.active')} value={n(data.campaigns.active)} testId="campaigns-active" />
              <Metric
                label={t('advertising.stats.live')}
                value={n(data.campaigns.live)}
                hint={t('advertising.stats.liveHint')}
                testId="campaigns-live"
              />
              <Metric label={t('advertising.stats.ended')} value={n(data.campaigns.ended)} testId="campaigns-ended" />
              <Metric label={t('advertising.stats.rejected')} value={n(data.campaigns.rejected)} testId="campaigns-rejected" />
              <Metric label={t('advertising.stats.cancelled')} value={n(data.campaigns.cancelled)} testId="campaigns-cancelled" />
            </div>
          </SectionCard>

          <SectionCard title={t('dashboard.company.payments')} headingLevel={2}>
            <CountGrid counts={data.payments} labelGroup="paymentStatus" testPrefix="payment" />
          </SectionCard>
        </div>
      )}
    </AsyncPage>
  )
}

/** Reuses the EXISTING owner dashboard endpoint; nothing is recomputed or duplicated. */
export function RealEstateOwnerDashboardView() {
  const { t, i18n } = useTranslation()
  const n = (value: number) => value.toLocaleString(i18n.language)
  return (
    <AsyncPage load={(signal) => realEstateApi.getOwnerDashboard(signal)}>
      {(data) => (
        <div className={styles.panel} data-testid="dashboard-owner">
          <SectionCard title={t('realEstateOwner.dashboard')} headingLevel={2}>
            <WorkspaceLinks links={[{ to: '/real-estate/owner', label: t('nav.realEstateWorkspace') }]} />
            <div className={styles.countGrid}>
              <Metric label={t('realEstateOwner.stats.total')} value={n(data.listings_total)} testId="listings-total" />
              <Metric label={t('realEstateOwner.stats.draft')} value={n(data.listings_draft)} testId="listings-draft" />
              <Metric
                label={t('realEstateOwner.stats.published')}
                value={n(data.listings_published)}
                testId="listings-published"
              />
              <Metric
                label={t('realEstateOwner.stats.visible')}
                value={n(data.listings_visible)}
                hint={t('realEstateOwner.stats.visibleHint')}
                testId="listings-visible"
              />
              <Metric
                label={t('realEstateOwner.stats.expired')}
                value={n(data.listings_expired)}
                hint={t('realEstateOwner.stats.expiredHint')}
                testId="listings-expired"
              />
              <Metric label={t('realEstateOwner.stats.sale')} value={n(data.listings_sale)} testId="listings-sale" />
              <Metric label={t('realEstateOwner.stats.rent')} value={n(data.listings_rent)} testId="listings-rent" />
            </div>
          </SectionCard>
        </div>
      )}
    </AsyncPage>
  )
}
