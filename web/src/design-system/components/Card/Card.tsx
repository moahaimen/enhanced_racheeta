import type { ElementType, HTMLAttributes, ReactNode } from 'react'

import styles from './Card.module.css'

export interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: ElementType
  /** Lifts on hover; use for clickable cards. */
  interactive?: boolean
  /** No inner padding (children manage their own). */
  flush?: boolean
  tone?: 'default' | 'brand'
  children: ReactNode
}

/** The base surface of every Racheeta block. */
export function Card({ as: Tag = 'div', interactive, flush, tone = 'default', className = '', children, ...rest }: CardProps) {
  const classes = [
    styles.card,
    interactive ? styles.interactive : '',
    flush ? styles.flush : '',
    tone === 'brand' ? styles.brand : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')
  return (
    <Tag {...rest} className={classes}>
      {children}
    </Tag>
  )
}

export interface SectionCardProps extends Omit<CardProps, 'title'> {
  title: ReactNode
  description?: ReactNode
  /** Right-side (inline-end) actions in the header. */
  actions?: ReactNode
  footer?: ReactNode
  headingLevel?: 2 | 3 | 4
  id?: string
}

/** A titled block: header (title, description, actions), body, optional footer. */
export function SectionCard({ title, description, actions, footer, headingLevel = 3, children, ...rest }: SectionCardProps) {
  const Heading: ElementType = `h${headingLevel}`
  return (
    <Card as="section" {...rest}>
      <header className={styles.header}>
        <div className={styles.headerText}>
          <Heading className={styles.title}>{title}</Heading>
          {description ? <p className={styles.description}>{description}</p> : null}
        </div>
        {actions ? <div className="cluster">{actions}</div> : null}
      </header>
      {children}
      {footer ? <footer className={styles.footer}>{footer}</footer> : null}
    </Card>
  )
}

/** Alias with dashboard semantics; same surface, same rules (real data only). */
export const DashboardBlock = SectionCard

export interface FeatureCardProps {
  icon: ReactNode
  title: ReactNode
  children: ReactNode
  action?: ReactNode
  /** Marks a module that is not implemented yet: no interaction, clear label. */
  upcoming?: ReactNode
  className?: string
}

export function FeatureCard({ icon, title, children, action, upcoming, className = '' }: FeatureCardProps) {
  return (
    <Card className={`${styles.feature} ${className}`.trim()} aria-disabled={upcoming ? true : undefined}>
      <span className={styles.featureIcon}>{icon}</span>
      <h3 className={styles.featureTitle}>{title}</h3>
      <p className={styles.featureBody}>{children}</p>
      {upcoming ? <div>{upcoming}</div> : action ? <div>{action}</div> : null}
    </Card>
  )
}

export interface StatCardProps {
  label: ReactNode
  value: ReactNode
  hint?: ReactNode
  className?: string
}

/** Displays a real number from the API. Never render placeholders or invented values. */
export function StatCard({ label, value, hint, className = '' }: StatCardProps) {
  return (
    <Card className={`${styles.stat} ${className}`.trim()}>
      <span className={styles.statLabel}>{label}</span>
      <span className={styles.statValue}>{value}</span>
      {hint ? <span className={styles.statHint}>{hint}</span> : null}
    </Card>
  )
}
