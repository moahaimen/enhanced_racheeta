import { useTranslation } from 'react-i18next'

import styles from './Spinner.module.css'

export interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  label?: string
  className?: string
}

/** Circular progress indicator. Announced to assistive tech via role="status". */
export function Spinner({ size = 'md', label, className = '' }: SpinnerProps) {
  const { t } = useTranslation()
  const text = label ?? t('common.loading')
  const sizeClass = size === 'sm' ? styles.sm : size === 'lg' ? styles.lg : ''
  return (
    <span role="status" aria-live="polite" className={`${styles.spinner} ${sizeClass} ${className}`.trim()}>
      <span className={styles.ring} aria-hidden="true" />
      <span className="visually-hidden">{text}</span>
    </span>
  )
}
