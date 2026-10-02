import { useTranslation } from 'react-i18next'

import { dashboards as dashboardsApi } from '../../api'
import { AsyncPage, SectionCard } from '../../design-system'
import styles from './Dashboard.module.css'
import { CountGrid, Metric, WorkspaceLinks } from './widgets'

export function AdminDashboardView() {
  const { t, i18n } = useTranslation()
  const n = (value: number) => value.toLocaleString(i18n.language)
  return (
    <AsyncPage load={(signal) => dashboardsApi.getAdmin(signal)}>
      {(d) => (
        <div className={styles.panel} data-testid="dashboard-admin">
          <SectionCard title={t('dashboard.admin.aggregatesOnly')} headingLevel={2}>
            <WorkspaceLinks links={[{ to: '/admin-console', label: t('nav.adminConsole') }]} />
          </SectionCard>

          <SectionCard title={t('dashboard.admin.accounts')} headingLevel={2}>
            <div className={styles.countGrid}>
              <Metric label={t('dashboard.total')} value={n(d.accounts.total)} testId="accounts-total" />
              <Metric label={t('dashboard.admin.active')} value={n(d.accounts.active)} testId="accounts-active" />
              <Metric label={t('dashboard.admin.inactive')} value={n(d.accounts.inactive)} testId="accounts-inactive" />
            </div>
            <CountGrid counts={d.accounts.by_role} labelGroup="roles" testPrefix="role" />
          </SectionCard>

          <SectionCard title={t('dashboard.admin.verification')} headingLevel={2}>
            <h3>{t('dashboard.admin.providers')}</h3>
            <CountGrid counts={d.providers.by_verification} labelGroup="verification" testPrefix="provider" />
            <h3>{t('dashboard.admin.companies')}</h3>
            <CountGrid counts={d.medical_companies.by_verification} labelGroup="verification" testPrefix="company" />
            <h3>{t('dashboard.admin.employers')}</h3>
            <CountGrid counts={d.employers.by_verification} labelGroup="verification" testPrefix="employer" />
            <Metric
              label={t('dashboard.admin.recruitmentSuspended')}
              value={n(d.employers.recruitment_suspended)}
              testId="employers-suspended"
            />
          </SectionCard>

          <SectionCard title={t('dashboard.admin.jobs')} headingLevel={2}>
            <CountGrid counts={d.jobs.by_status} labelGroup="jobStatus" testPrefix="job" />
          </SectionCard>

          <SectionCard title={t('dashboard.admin.reservations')} headingLevel={2}>
            <CountGrid counts={d.reservations.by_status} labelGroup="reservationStatus" testPrefix="reservation" />
          </SectionCard>

          <SectionCard title={t('dashboard.admin.catalogue')} headingLevel={2}>
            <div className="grid-2">
              <Metric label={t('company.productsTotal')} value={n(d.marketplace.products.total)} testId="products-total" />
              <Metric label={t('company.productsActive')} value={n(d.marketplace.products.active)} testId="products-active" />
            </div>
            <CountGrid counts={d.real_estate.listings_by_status} labelGroup="publicationStatus" testPrefix="listing" />
          </SectionCard>

          <SectionCard title={t('dashboard.admin.advertising')} headingLevel={2}>
            <CountGrid counts={d.advertising.campaigns_by_status} labelGroup="campaignStatus" testPrefix="campaign" />
            <CountGrid counts={d.advertising.payments_by_status} labelGroup="paymentStatus" testPrefix="payment" />
          </SectionCard>

          <SectionCard title={t('dashboard.admin.billing')} headingLevel={2}>
            <CountGrid counts={d.billing.subscriptions_by_status} labelGroup="subscriptionStatus" testPrefix="subscription" />
          </SectionCard>

          <SectionCard title={t('dashboard.admin.audit')} headingLevel={2}>
            <div className="grid-2">
              <Metric label={t('dashboard.admin.last24h')} value={n(d.audit.last_24_hours)} testId="audit-24h" />
              <Metric label={t('dashboard.admin.last7d')} value={n(d.audit.last_7_days)} testId="audit-7d" />
            </div>
          </SectionCard>
        </div>
      )}
    </AsyncPage>
  )
}
