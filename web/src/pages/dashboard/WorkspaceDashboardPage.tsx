import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { workspaces as workspacesApi } from '../../api'
import type { DashboardItem, DashboardModule, DashboardStat, Workspace, WorkspaceDashboard } from '../../api'
import { useAuth } from '../../auth/useAuth'
import {
  AsyncPage,
  Badge,
  Container,
  Icon,
  LinkButton,
  PageHeader,
  PageStack,
  SectionCard,
  Select,
  type BadgeTone,
  type IconName,
} from '../../design-system'
import { useAsyncData } from '../../hooks/useAsync'
import { pickScript } from '../../i18n/localized'
import { SponsoredSection } from '../advertising/SponsoredSection'
import { PromotedPropertiesSection } from '../realEstate/PromotionsPanels'
import styles from './WorkspaceDashboard.module.css'

const KIND_ICON: Record<string, IconName> = {
  patient: 'user',
  practitioner: 'stethoscope',
  facility: 'hospital',
  company: 'building',
  property: 'home',
  employer: 'briefcase',
  job_seeker: 'user',
  admin: 'shieldCheck',
}

/** Status values the backend sends as stat values (rendered through their own label groups). */
const VALUE_GROUP: Record<string, string> = {
  verification: 'verification',
  profession: 'professions',
  subscription: 'subscriptionStatus',
}

const FEEDS = new Set(['sponsored', 'promoted'])

/**
 * /dashboard — ONE page for every account type. The SERVER composes the modules for the selected
 * workspace (kind, subtype and the caller's current capabilities) and refuses foreign or revoked
 * workspaces; this page only renders what it receives.
 *
 * Switching workspace changes `?ws=`; the dashboard body is keyed by account + workspace, so every
 * switch (or account change) remounts it: previous workspace data is dropped, the in-flight request
 * is aborted, and nothing from the previous organization can render.
 */
export function WorkspaceDashboardPage() {
  const { account } = useAuth()
  const [params] = useSearchParams()
  const ws = params.get('ws')
  return (
    <Container width="xl">
      <DashboardBody key={`${account?.id ?? 'anonymous'}|${ws ?? 'default'}`} ws={ws} />
    </Container>
  )
}

function DashboardBody({ ws }: { ws: string | null }) {
  return (
    <AsyncPage load={(signal) => workspacesApi.getWorkspaceDashboard(ws, signal)}>
      {(dashboard) => (
        <>
          <DashboardHeader dashboard={dashboard} />
          <PageStack>
            <PrimaryActions dashboard={dashboard} />
            <div className={styles.grid} data-testid={`workspace-dashboard-${dashboard.workspace.kind}`}>
              {dashboard.modules.map((module) =>
                FEEDS.has(module.key) ? (
                  <div key={module.key} className={styles.wide}>
                    {module.key === 'sponsored' ? <SponsoredSection /> : <PromotedPropertiesSection />}
                  </div>
                ) : (
                  <ModuleCard key={`${module.key}:${module.variant}`} module={module} />
                ),
              )}
            </div>
          </PageStack>
        </>
      )}
    </AsyncPage>
  )
}

function DashboardHeader({ dashboard }: { dashboard: WorkspaceDashboard }) {
  const { t, i18n } = useTranslation()
  const { workspace } = dashboard
  const subtype = workspace.subtype
    ? t(`accountTypes.${workspace.subtype}`, { defaultValue: t(`professions.${workspace.subtype}`, { defaultValue: '' }) })
    : ''
  return (
    <PageHeader
      eyebrow={
        <>
          <Icon name={KIND_ICON[workspace.kind] ?? 'chart'} size={16} />
          {t(`ws.kinds.${workspace.kind}`, { defaultValue: workspace.kind })}
          {subtype ? ` · ${subtype}` : ''}
        </>
      }
      title={pickScript(workspace.title, i18n.language)}
      description={
        <span className={styles.who}>
          {t('dash.greeting', { name: pickScript(dashboard.header.name, i18n.language) })}
          {workspace.role && workspace.kind !== 'patient' ? (
            <Badge tone="brand">{t(`ws.roles.${workspace.role}`, { defaultValue: workspace.role })}</Badge>
          ) : null}
          {workspace.verification_status ? (
            <Badge tone={workspace.verification_status === 'VERIFIED' ? 'success' : 'warning'}>
              {t(`verification.${workspace.verification_status}`, { defaultValue: workspace.verification_status })}
            </Badge>
          ) : null}
        </span>
      }
      actions={<WorkspaceSwitcher current={workspace.id} />}
    />
  )
}

/** Lists only the workspaces the server returns; choosing one reloads the dashboard for it. */
function WorkspaceSwitcher({ current }: { current: string }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const list = useAsyncData((signal) => workspacesApi.listWorkspaces(signal), [])
  const items: Workspace[] = list.data ?? []
  if (items.length < 2) return null
  return (
    <div className={styles.switcher}>
      <Select
        label={t('dash.switchWorkspace')}
        value={current}
        onChange={(e) => navigate(`/dashboard?ws=${encodeURIComponent(e.target.value)}`)}
        data-testid="workspace-switcher"
      >
        {items.map((w) => (
          <option key={w.id} value={w.id}>
            {pickScript(w.title, i18n.language)} — {t(`ws.kinds.${w.kind}`, { defaultValue: w.kind })}
            {w.role && w.kind !== 'patient' ? ` (${t(`ws.roles.${w.role}`, { defaultValue: w.role })})` : ''}
          </option>
        ))}
      </Select>
    </div>
  )
}

function PrimaryActions({ dashboard }: { dashboard: WorkspaceDashboard }) {
  const { t } = useTranslation()
  return (
    <nav className={styles.actions} aria-label={t('dash.primaryActions')}>
      {dashboard.actions.map((action, index) => (
        <LinkButton key={action.key} to={action.path} size="sm" variant={index === 0 ? 'primary' : 'secondary'}>
          {t(`dash.actions.${action.key}`, { defaultValue: action.key })}
        </LinkButton>
      ))}
      <LinkButton to="/dashboard/summary" size="sm" variant="ghost">
        {t('dash.classic')}
      </LinkButton>
    </nav>
  )
}

function humanize(key: string) {
  return key.replace(/_/g, ' ')
}

function useStatValue() {
  const { t, i18n } = useTranslation()
  return (stat: DashboardStat) => {
    const { value } = stat
    if (value === null || value === '') return '—'
    if (typeof value === 'boolean') return value ? t('dash.yes') : t('dash.no')
    if (typeof value === 'number') return value.toLocaleString(i18n.language, { maximumFractionDigits: 2 })
    const group = VALUE_GROUP[stat.key]
    return group ? t(`${group}.${value}`, { defaultValue: value }) : value
  }
}

function ModuleCard({ module }: { module: DashboardModule }) {
  const { t } = useTranslation()
  const value = useStatValue()
  const title = module.variant
    ? t(`dash.modules.${module.key}_${module.variant}`, { defaultValue: t(`dash.modules.${module.key}`, { defaultValue: humanize(module.key) }) })
    : t(`dash.modules.${module.key}`, { defaultValue: humanize(module.key) })
  return (
    <SectionCard
      title={title}
      headingLevel={2}
      actions={
        module.link && module.key !== 'account' ? (
          <LinkButton to={module.link} size="sm" variant="ghost">
            {t('dash.open')}
          </LinkButton>
        ) : null
      }
    >
      <div data-testid={`module-${module.key}`} className="stack-sm">
        {module.stats.length > 0 ? (
          <dl className={styles.stats}>
            {module.stats.map((stat) => (
              <div key={stat.key} className={styles.stat}>
                <dt>{t(`dash.stats.${stat.key}`, { defaultValue: humanize(stat.key) })}</dt>
                <dd data-testid={`stat-${module.key}-${stat.key}`}>{value(stat)}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        {module.key === 'account' ? (
          <div className={styles.links}>
            {module.items.map((item) => (
              <LinkButton key={item.id} to={item.path} size="sm" variant="secondary">
                {t(`dash.account.${item.id}`)}
              </LinkButton>
            ))}
          </div>
        ) : module.items.length > 0 ? (
          <ul className={styles.rows}>
            {module.items.map((item) => (
              <ItemRow key={item.id} item={item} />
            ))}
          </ul>
        ) : null}
      </div>
    </SectionCard>
  )
}

const TONE: Record<string, BadgeTone> = {
  ACTIVE: 'success',
  ACCEPTED: 'success',
  DELIVERED: 'success',
  PUBLISHED: 'success',
  COMPLETED: 'brand',
  CONFIRMED: 'brand',
  QUOTED: 'brand',
  PENDING: 'warning',
  PLACED: 'warning',
  REQUESTED: 'warning',
  SUBMITTED: 'warning',
  LOW: 'warning',
  PENDING_PAYMENT: 'warning',
  REJECTED: 'error',
  OUT: 'error',
}

function ItemRow({ item }: { item: DashboardItem }) {
  const { t, i18n } = useTranslation()
  const title = item.status_group === 'dash.step' ? t(`dash.steps.${item.title}`) : pickScript(item.title, i18n.language)
  const isDate = /^\d{4}-\d{2}-\d{2}T/.test(item.subtitle)
  const subtitle = isDate ? new Date(item.subtitle).toLocaleString(i18n.language) : pickScript(item.subtitle, i18n.language)
  return (
    <li className={styles.row}>
      <div className={styles.rowHead}>
        <span className={styles.rowTitle}>{item.path ? <Link to={item.path}>{title}</Link> : title}</span>
        {item.status ? (
          <Badge tone={TONE[item.status] ?? 'neutral'}>
            {item.status_group ? t(`${item.status_group}.${item.status}`, { defaultValue: item.status }) : item.status}
          </Badge>
        ) : null}
      </div>
      {subtitle ? <span className={styles.rowMeta}>{subtitle}</span> : null}
    </li>
  )
}
