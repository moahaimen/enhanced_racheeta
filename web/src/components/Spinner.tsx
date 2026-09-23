import { useTranslation } from 'react-i18next'

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  label?: string
  className?: string
}

/** Circular progress indicator. Announced to assistive tech via role="status". */
export function Spinner({ size = 'md', label, className = '' }: SpinnerProps) {
  const { t } = useTranslation()
  const text = label ?? t('common.loading')
  return (
    <span role="status" aria-live="polite" className={`spinner spinner--${size} ${className}`.trim()}>
      <span className="spinner__ring" aria-hidden="true" />
      <span className="visually-hidden">{text}</span>
    </span>
  )
}
