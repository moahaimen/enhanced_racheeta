import { useState, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { useTranslation } from 'react-i18next'

import { Icon } from '../../icons'
import styles from './Form.module.css'
import { FormField } from './FormField'

interface CommonFieldProps {
  label: ReactNode
  optional?: boolean
  hint?: ReactNode
  error?: string | undefined
  className?: string
}

export interface TextFieldProps extends CommonFieldProps, Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'className'> {
  leading?: ReactNode
  /** Rendered after the input (e.g. a toggle button). */
  trailing?: ReactNode
}

export function TextField({ label, optional, hint, error, className, leading, trailing, ...input }: TextFieldProps) {
  const { t } = useTranslation()
  return (
    <FormField label={label} optional={optional} hint={hint} error={error} className={className}>
      {(a11y) => (
        <div className={`${styles.control} ${leading ? styles.withLeading : ''}`.trim()}>
          {leading ? <span className={styles.leading}>{leading}</span> : null}
          <input className={styles.input} {...a11y} {...input} aria-label={typeof label === 'string' ? undefined : t('common.search')} />
          {trailing}
        </div>
      )}
    </FormField>
  )
}

export function PasswordField(props: Omit<TextFieldProps, 'type' | 'trailing' | 'leading'>) {
  const { t } = useTranslation()
  const [visible, setVisible] = useState(false)
  return (
    <TextField
      {...props}
      type={visible ? 'text' : 'password'}
      trailing={
        <button
          type="button"
          className={styles.trailingButton}
          aria-pressed={visible}
          onClick={() => setVisible((v) => !v)}
        >
          <Icon name={visible ? 'eyeOff' : 'eye'} size={18} />
          <span className="visually-hidden">{visible ? t('fields.hidePassword') : t('fields.showPassword')}</span>
        </button>
      }
    />
  )
}

export interface SearchFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'className'> {
  label: string
  className?: string
}

/** Standalone search input with a leading icon and a visually hidden label. */
export function SearchField({ label, className = '', ...input }: SearchFieldProps) {
  return (
    <div className={`${styles.control} ${styles.withLeading} ${className}`.trim()}>
      <span className={styles.leading}>
        <Icon name="search" size={18} />
      </span>
      <input type="search" className={styles.input} aria-label={label} {...input} />
    </div>
  )
}

export interface SelectProps extends CommonFieldProps, Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id' | 'className'> {
  children: ReactNode
  /** Small inline indicator (e.g. a spinner while options load). */
  adornment?: ReactNode
}

export function Select({ label, optional, hint, error, className, children, adornment, ...select }: SelectProps) {
  return (
    <FormField
      label={
        adornment ? (
          <>
            {label} {adornment}
          </>
        ) : (
          label
        )
      }
      optional={optional}
      hint={hint}
      error={error}
      className={className}
    >
      {(a11y) => (
        <div className={styles.control}>
          <select className={styles.input} {...a11y} {...select}>
            {children}
          </select>
        </div>
      )}
    </FormField>
  )
}

export interface TextareaProps extends CommonFieldProps, Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id' | 'className'> {}

export function Textarea({ label, optional, hint, error, className, ...textarea }: TextareaProps) {
  return (
    <FormField label={label} optional={optional} hint={hint} error={error} className={className}>
      {(a11y) => (
        <div className={styles.control}>
          <textarea className={styles.input} rows={4} {...a11y} {...textarea} />
        </div>
      )}
    </FormField>
  )
}

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'className'> {
  label: ReactNode
  className?: string
}

export function Checkbox({ label, className = '', ...input }: CheckboxProps) {
  return (
    <label className={`${styles.check} ${className}`.trim()}>
      <input type="checkbox" {...input} />
      <span>{label}</span>
    </label>
  )
}

export interface CheckboxGroupProps {
  legend: ReactNode
  error?: string | undefined
  children: ReactNode
}

export function CheckboxGroup({ legend, error, children }: CheckboxGroupProps) {
  return (
    <div className={`${styles.field} ${error ? styles.invalid : ''}`.trim()}>
      <fieldset className={styles.checkGroup}>
        <legend className={styles.label}>{legend}</legend>
        {children}
      </fieldset>
      {error ? (
        <p className={styles.error} role="alert">
          <Icon name="alertCircle" size={14} />
          {error}
        </p>
      ) : null}
    </div>
  )
}

export interface FormSectionProps {
  title: ReactNode
  description?: ReactNode
  children: ReactNode
}

/** Groups related fields inside a form with a heading and divider. */
export function FormSection({ title, description, children }: FormSectionProps) {
  return (
    <div className={styles.section}>
      <h4 className={styles.sectionTitle}>{title}</h4>
      {description ? <p className={styles.sectionDescription}>{description}</p> : null}
      {children}
    </div>
  )
}

export function FormActions({ children }: { children: ReactNode }) {
  return <div className={styles.actions}>{children}</div>
}
