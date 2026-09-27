import { useTranslation } from 'react-i18next'

import type { Entitlement } from '../../../api'
import { Badge } from '../Badge/Badge'
import styles from './UsageMeter.module.css'

/** Renders one entitlement from the billing summary. Real numbers only. */
export function UsageMeter({ entitlement, current }: { entitlement: Entitlement; current?: number }) {
  const { t } = useTranslation()
  const label = t(`entitlements.${entitlement.key}`, { defaultValue: entitlement.key })
  if (entitlement.kind === 'BOOLEAN') {
    return (
      <div className={`${styles.meter} ${entitlement.enabled ? '' : styles.disabled}`.trim()}>
        <div className={styles.row}>
          <span className={styles.label}>{label}</span>
          <Badge tone={entitlement.enabled ? 'success' : 'neutral'}>{entitlement.enabled ? t('common.yes') : t('common.no')}</Badge>
        </div>
      </div>
    )
  }
  const used = current ?? entitlement.used
  const limit = entitlement.limit
  const capacity = limit === null ? null : limit + entitlement.credits
  const ratio = capacity ? Math.min(used / capacity, 1) : 0
  const fillClass = ratio >= 1 ? styles.fillFull : ratio >= 0.8 ? styles.fillWarn : ''
  return (
    <div className={`${styles.meter} ${entitlement.enabled ? '' : styles.disabled}`.trim()}>
      <div className={styles.row}>
        <span className={styles.label}>{label}</span>
        <span className={styles.value} dir="ltr">
          {limit === null ? `${used} / ${t('common.unlimited')}` : `${used} / ${capacity}`}
          {entitlement.credits > 0 ? ` (+${entitlement.credits})` : ''}
        </span>
      </div>
      {limit !== null ? (
        <div className={styles.track} role="progressbar" aria-valuemin={0} aria-valuemax={capacity ?? 0} aria-valuenow={used} aria-label={label}>
          <span className={`${styles.fill} ${fillClass}`.trim()} style={{ inlineSize: `${ratio * 100}%` }} />
        </div>
      ) : null}
    </div>
  )
}
