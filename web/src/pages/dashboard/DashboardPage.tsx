import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { dashboards as dashboardsApi } from '../../api'
import type { DashboardKey } from '../../api'
import { useAuth } from '../../auth/useAuth'
import {
  AsyncPage,
  Container,
  EmptyState,
  Icon,
  LinkButton,
  PageHeader,
  PageStack,
  Tabs,
  tabPanelProps,
} from '../../design-system'
import { AdminDashboardView } from './AdminDashboard'
import { MedicalCompanyDashboardView, RealEstateOwnerDashboardView } from './BusinessDashboards'
import { PatientDashboard } from './PatientDashboard'
import { DoctorDashboard, FacilityDashboardView } from './ProviderDashboard'
import { RecruiterDashboardView } from './RecruiterDashboard'

const VIEWS: Record<DashboardKey, () => React.JSX.Element> = {
  patient: PatientDashboard,
  doctor: DoctorDashboard,
  facility: FacilityDashboardView,
  medical_company: MedicalCompanyDashboardView,
  real_estate_owner: RealEstateOwnerDashboardView,
  recruiter: RecruiterDashboardView,
  admin: AdminDashboardView,
}

/**
 * /dashboard — one role-aware entry point. The SERVER decides which dashboards the signed-in
 * account can open (`GET /dashboards/`); the page never infers it from the role. Only the selected
 * dashboard loads, nothing polls, and everything is keyed by the account so another account can
 * never see this one's data.
 */
export function DashboardPage() {
  const { t } = useTranslation()
  const { account } = useAuth()
  return (
    <Container width="xl">
      <PageHeader
        eyebrow={
          <>
            <Icon name="chart" size={16} />
            {t('nav.dashboard')}
          </>
        }
        title={t('dashboard.title')}
        description={t('dashboard.intro')}
      />
      <PageStack>
        <DashboardHub key={account?.id ?? 'anonymous'} />
      </PageStack>
    </Container>
  )
}

function DashboardHub() {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<DashboardKey | null>(null)
  return (
    <AsyncPage load={(signal) => dashboardsApi.getIndex(signal)}>
      {({ dashboards }) => {
        if (dashboards.length === 0) {
          return (
            <div className="card-block">
              <EmptyState icon="chart" title={t('dashboard.none')} testId="dashboard-none">
                {t('dashboard.noneHint')}
              </EmptyState>
              <LinkButton to="/profile" variant="secondary">
                {t('nav.profile')}
              </LinkButton>
            </div>
          )
        }
        const active = selected && dashboards.includes(selected) ? selected : dashboards[0]!
        const View = VIEWS[active]
        return (
          <>
            {dashboards.length > 1 ? (
              <Tabs
                id="dashboard"
                aria-label={t('dashboard.tabsLabel')}
                tabs={dashboards.map((key) => ({ id: key, label: t(`dashboard.tabs.${key}`) }))}
                value={active}
                onChange={(id) => setSelected(id as DashboardKey)}
              />
            ) : null}
            <div {...(dashboards.length > 1 ? tabPanelProps('dashboard', active) : {})}>
              <View key={active} />
            </div>
          </>
        )
      }}
    </AsyncPage>
  )
}
