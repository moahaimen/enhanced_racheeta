import { useId, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Icon } from '../../icons'
import styles from './Form.module.css'

export interface FormFieldRenderProps {
  id: string
  'aria-invalid': true | undefined
  'aria-describedby': string | undefined
}

export interface FormFieldProps {
  label: ReactNode
  optional?: boolean
  hint?: ReactNode
  error?: string | undefined
  /** Extra class on the wrapper. */
  className?: string
  /** Receives the ids that associate the control with its label, hint and error. */
  children: (props: FormFieldRenderProps) => ReactNode
}

/** Label + control + hint + error with the correct associations. */
export function FormField({ label, optional, hint, error, className = '', children }: FormFieldProps) {
  const { t } = useTranslation()
  const id = useId()
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(' ') || undefined
  return (
    <div className={`${styles.field} ${error ? styles.invalid : ''} ${className}`.trim()}>
      <label className={styles.label} htmlFor={id}>
        {label}
        {optional ? <span className={styles.optional}> · {t('common.optional')}</span> : null}
      </label>
      {children({ id, 'aria-invalid': error ? true : undefined, 'aria-describedby': describedBy })}
      {hint ? (
        <div id={hintId} className={styles.hint}>
          {hint}
        </div>
      ) : null}
      {error ? (
        <p id={errorId} className={styles.error} role="alert">
          <Icon name="alertCircle" size={14} />
          {error}
        </p>
      ) : null}
    </div>
  )
}
