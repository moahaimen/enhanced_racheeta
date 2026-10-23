import type { ReactNode } from 'react'
import { Link, type To } from 'react-router'

import { Icon, type IconName } from '../../icons'
import styles from './Tiles.module.css'

export type Accent = 'teal' | 'blue' | 'indigo' | 'coral' | 'mint' | 'aqua'

/** Large icon shortcut used for the category row. One accent family per product area. */
export function CategoryTile({ to, icon, label, accent = 'teal' }: { to: To; icon: IconName; label: string; accent?: Accent }) {
  return (
    <Link to={to} className={styles.tile} data-accent={accent}>
      <span className={styles.tileIcon} aria-hidden="true">
        <Icon name={icon} size={28} />
      </span>
      <span className={styles.tileLabel}>{label}</span>
    </Link>
  )
}

/** Illustrated service card: art on top, title + description, arrow call-to-action. */
export function ServiceTile({ to, state, art, title, description, accent = 'teal' }: { to: To; state?: unknown; art: ReactNode; title: string; description: string; accent?: Accent }) {
  return (
    <Link to={to} state={state} className={styles.service} data-accent={accent}>
      <span className={styles.serviceArt} aria-hidden="true">
        {art}
      </span>
      <span className={styles.serviceBody}>
        <span className={styles.serviceText}>
          <span className={styles.serviceTitle}>{title}</span>
          <span className={styles.serviceDesc}>{description}</span>
        </span>
        <span className={styles.arrow} aria-hidden="true">
          <Icon name="arrowForward" size={18} flipInRtl />
        </span>
      </span>
    </Link>
  )
}

/** Compact stat chip: a REAL number from the API next to a label. */
export function StatChip({ icon, value, label }: { icon: IconName; value: ReactNode; label: string }) {
  return (
    <li className={styles.stat}>
      <span className={styles.statIcon} aria-hidden="true">
        <Icon name={icon} size={20} />
      </span>
      <span>
        <strong className={styles.statValue}>{value}</strong>
        <span className={styles.statLabel}>{label}</span>
      </span>
    </li>
  )
}
