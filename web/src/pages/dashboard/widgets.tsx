import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ReservationBrief } from '../../api'
import { Badge, EmptyState, LinkButton, StatCard, type BadgeTone } from '../../design-system'
import styles from './Dashboard.module.css'

/** A real number from the API; `testId` lets tests address one metric without guessing markup. */
export function Metric({
  label,
  value,
  hint,
  testId,
}: {
  label: ReactNode
  value: ReactNode
  hint?: ReactNode
  testId: string
}) {
  return <StatCard label={label} value={<span data-testid={testId}>{value}</span>} hint={hint} />
}

/**
 * One StatCard per key of a zero-filled count map. Labels come from an existing i18n group
 * (`reservationStatus`, `jobStatus`, …) so wording stays identical across the product.
 */
export function CountGrid({
  counts,
  labelGroup,
  testPrefix,
}: {
  counts: Record<string, number>
  labelGroup: string
  testPrefix: string
}) {
  const { t, i18n } = useTranslation()
  return (
    <div className={styles.countGrid}>
      {Object.entries(counts).map(([key, value]) => (
        <Metric
          key={key}
          label={t(`${labelGroup}.${key}`, { defaultValue: key })}
          value={value.toLocaleString(i18n.language)}
          testId={`${testPrefix}-${key}`}
        />
      ))}
    </div>
  )
}

const STATUS_TONE: Record<string, BadgeTone> = {
  PENDING: 'warning',
  CONFIRMED: 'success',
  COMPLETED: 'brand',
  REJECTED: 'error',
  CANCELLED: 'neutral',
  NO_SHOW: 'error',
}

export function ReservationRows({
  rows,
  patientName,
  testId,
}: {
  rows: (ReservationBrief & { patient_name?: string })[]
  patientName?: boolean
  testId: string
}) {
  const { t, i18n } = useTranslation()
  if (rows.length === 0) {
    return <EmptyState icon="calendar" title={t('dashboard.noReservations')} testId={`${testId}-empty`} />
  }
  return (
    <ul className={styles.rows} data-testid={testId}>
      {rows.map((row) => (
        <li key={row.id} className={styles.row}>
          <div className={styles.rowHead}>
            <h3 className={styles.rowTitle}>{row.service_title_snapshot}</h3>
            <Badge tone={STATUS_TONE[row.status] ?? 'neutral'}>{t(`reservationStatus.${row.status}`)}</Badge>
          </div>
          <p className={styles.rowMeta}>
            {patientName && row.patient_name ? `${row.patient_name} · ` : `${row.provider_name_snapshot} · `}
            <time dateTime={row.starts_at}>{new Date(row.starts_at).toLocaleString(i18n.language)}</time>
          </p>
        </li>
      ))}
    </ul>
  )
}

export function UnreadBlock({ notifications, messages }: { notifications: number; messages: number }) {
  const { t, i18n } = useTranslation()
  return (
    <div className="grid-2">
      <Metric
        label={t('dashboard.unreadNotifications')}
        value={notifications.toLocaleString(i18n.language)}
        testId="unread-notifications"
      />
      <Metric
        label={t('dashboard.unreadMessages')}
        value={messages.toLocaleString(i18n.language)}
        testId="unread-messages"
      />
    </div>
  )
}

export function WorkspaceLinks({ links }: { links: { to: string; label: string }[] }) {
  return (
    <div className={styles.links}>
      {links.map((link) => (
        <LinkButton key={link.to} to={link.to} variant="secondary" size="sm">
          {link.label}
        </LinkButton>
      ))}
    </div>
  )
}
