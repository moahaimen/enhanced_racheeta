import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link } from 'react-router'

import { Spinner } from '../Spinner/Spinner'
import styles from './Button.module.css'
import { buttonClassName } from './buttonClassName'

import type { ButtonSize, ButtonVariant } from './buttonClassName'

interface ButtonBaseProps {
  variant?: ButtonVariant
  size?: ButtonSize
  /** Shows the circular indicator, keeps the dimensions, disables interaction. */
  loading?: boolean
  loadingLabel?: ReactNode
  leading?: ReactNode
  trailing?: ReactNode
  block?: boolean
  className?: string
  children: ReactNode
}

export interface ButtonProps
  extends ButtonBaseProps, Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children' | 'className'> {}

/** The Racheeta button. Every backend-connected button uses `ApiActionButton`, which builds on this. */
export function Button({
  variant,
  size,
  loading = false,
  loadingLabel,
  leading,
  trailing,
  block,
  className,
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      className={buttonClassName({ variant, size, block, className })}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      <span className={`${styles.content} ${loading ? styles.contentHidden : ''}`.trim()} aria-hidden={loading || undefined}>
        {leading}
        <span>{children}</span>
        {trailing}
      </span>
      {loading ? (
        <span className={styles.loading}>
          <Spinner size="sm" />
          {loadingLabel ? <span className={styles.loadingLabel}>{loadingLabel}</span> : null}
        </span>
      ) : null}
    </button>
  )
}

export interface LinkButtonProps extends ButtonBaseProps {
  to: string
  replace?: boolean
}

/** A router link styled as a button (navigation, never a backend action). */
export function LinkButton({ to, replace, variant, size, block, className, leading, trailing, children }: LinkButtonProps) {
  return (
    <Link to={to} replace={replace} className={buttonClassName({ variant, size, block, className })}>
      <span className={styles.content}>
        {leading}
        <span>{children}</span>
        {trailing}
      </span>
    </Link>
  )
}

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  /** Required: the accessible name. */
  label: string
  variant?: ButtonVariant
  size?: ButtonSize
  children: ReactNode
}

export function IconButton({ label, variant = 'ghost', size = 'md', className = '', type = 'button', ...rest }: IconButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      aria-label={label}
      title={label}
      className={`${buttonClassName({ variant, size })} ${styles.iconButton} ${className}`.trim()}
    />
  )
}
