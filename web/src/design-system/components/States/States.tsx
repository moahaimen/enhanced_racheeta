import type { CSSProperties, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { toErrorMessage } from '../../../hooks/useAsync'
import { Icon, type IconName } from '../../icons'
import { Button } from '../Button/Button'
import { Spinner } from '../Spinner/Spinner'
import styles from './States.module.css'

export interface EmptyStateProps {
  icon?: IconName
  title: ReactNode
  children?: ReactNode
  action?: ReactNode
  testId?: string
}

export function EmptyState({ icon = 'search', title, children, action, testId }: EmptyStateProps) {
  return (
    <div className={styles.state} data-testid={testId}>
      <span className={styles.icon}>
        <Icon name={icon} size={26} />
      </span>
      <p className={styles.title}>{title}</p>
      {children ? <p className={styles.body}>{children}</p> : null}
      {action}
    </div>
  )
}

export interface ErrorStateProps {
  error?: unknown
  title?: ReactNode
  onRetry?: () => void
  testId?: string
}

export function ErrorState({ error, title, onRetry, testId }: ErrorStateProps) {
  const { t } = useTranslation()
  return (
    <div className={styles.state} role="alert" data-testid={testId}>
      <span className={`${styles.icon} ${styles.iconError}`}>
        <Icon name="alertCircle" size={26} />
      </span>
      <p className={styles.title}>{title ?? t('common.error')}</p>
      <p className={styles.body}>{toErrorMessage(error, t('errors.unknown'))}</p>
      {onRetry ? (
        <Button variant="secondary" onClick={onRetry} leading={<Icon name="refresh" size={18} />}>
          {t('common.retry')}
        </Button>
      ) : null}
    </div>
  )
}

export interface LoadingStateProps {
  label?: string
  testId?: string
}

export function LoadingState({ label, testId }: LoadingStateProps) {
  const { t } = useTranslation()
  return (
    <div className={styles.state} data-testid={testId}>
      <Spinner size="lg" label={label} />
      <p className={styles.body}>{label ?? t('common.loading')}</p>
    </div>
  )
}

export interface SkeletonProps {
  height?: string
  width?: string
  circle?: boolean
  className?: string
}

/** Shimmer placeholder for content whose shape is known while it loads. */
export function Skeleton({ height = '1rem', width = '100%', circle = false, className = '' }: SkeletonProps) {
  const style = { '--skeleton-height': height, inlineSize: width } as CSSProperties
  return <span className={`${styles.skeleton} ${circle ? styles.skeletonCircle : ''} ${className}`.trim()} style={style} aria-hidden="true" />
}

export interface LoadingOverlayProps {
  active: boolean
  label?: string
  children?: ReactNode
}

/** Dims its children and shows a spinner while `active`. Blocks interaction. */
export function LoadingOverlay({ active, label, children }: LoadingOverlayProps) {
  return (
    <div className={styles.overlayHost} aria-busy={active}>
      <div inert={active || undefined}>{children}</div>
      {active ? (
        <div className={styles.overlay} data-testid="loading-overlay">
          <Spinner size="lg" label={label} />
        </div>
      ) : null}
    </div>
  )
}
