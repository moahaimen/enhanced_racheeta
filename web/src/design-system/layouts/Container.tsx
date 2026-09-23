import type { ElementType, HTMLAttributes, ReactNode } from 'react'

import styles from './Container.module.css'

export interface ContainerProps extends HTMLAttributes<HTMLElement> {
  as?: ElementType
  width?: 'sm' | 'md' | 'lg' | 'xl'
  /** Vertical section padding. */
  section?: boolean | 'tight'
  children: ReactNode
}

/** Centred content column with the page gutter. */
export function Container({ as: Tag = 'div', width = 'lg', section = false, className = '', children, ...rest }: ContainerProps) {
  const classes = [
    styles.container,
    width !== 'lg' ? styles[width] : '',
    section === true ? styles.section : section === 'tight' ? styles.sectionTight : '',
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

/** Vertical rhythm between blocks on a page. */
export function PageStack({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`${styles.stack} ${className}`.trim()}>{children}</div>
}

export interface PageHeaderProps {
  eyebrow?: ReactNode
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
}

export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <header className={styles.pageHeader}>
      <div className={styles.pageHeaderText}>
        {eyebrow ? <div className={styles.eyebrow}>{eyebrow}</div> : null}
        <h1 className={styles.pageTitle}>{title}</h1>
        {description ? <p className={styles.pageDescription}>{description}</p> : null}
      </div>
      {actions ? <div className="cluster">{actions}</div> : null}
    </header>
  )
}

export interface SectionHeaderProps {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  headingLevel?: 2 | 3
}

export function SectionHeader({ title, description, actions, headingLevel = 2 }: SectionHeaderProps) {
  const Heading: ElementType = `h${headingLevel}`
  return (
    <header className={styles.sectionHeader}>
      <div>
        <Heading className={styles.sectionTitle}>{title}</Heading>
        {description ? <p className={styles.sectionDescription}>{description}</p> : null}
      </div>
      {actions ? <div className="cluster">{actions}</div> : null}
    </header>
  )
}
