import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Card, Container, Icon } from '../../design-system'
import styles from './AuthShell.module.css'

export interface AuthShellProps {
  title: ReactNode
  description?: ReactNode
  children: ReactNode
  footer?: ReactNode
}

/** Two-panel authentication layout: brand side (desktop) + form card. */
export function AuthShell({ title, description, children, footer }: AuthShellProps) {
  const { t } = useTranslation()
  return (
    <Container width="lg">
      <div className={styles.shell}>
        <aside className={styles.side} aria-hidden="true">
          <div>
            <h2 className={styles.sideTitle}>{t('auth.sideTitle')}</h2>
            <p className={styles.sideBody}>{t('auth.sideBody')}</p>
          </div>
          <ul className={styles.sideList}>
            <li>
              <span className={styles.sideIcon}>
                <Icon name="shieldCheck" size={18} />
              </span>
              {t('home.heroTrust1')}
            </li>
            <li>
              <span className={styles.sideIcon}>
                <Icon name="user" size={18} />
              </span>
              {t('home.heroTrust2')}
            </li>
            <li>
              <span className={styles.sideIcon}>
                <Icon name="globe" size={18} />
              </span>
              {t('home.heroTrust3')}
            </li>
          </ul>
        </aside>
        <Card className={styles.panel}>
          <div className={styles.heading}>
            <h1>{title}</h1>
            {description ? <p>{description}</p> : null}
          </div>
          {children}
          {footer ? <div className={styles.footer}>{footer}</div> : null}
        </Card>
      </div>
    </Container>
  )
}

export function AuthSuccess({ children }: { children: ReactNode }) {
  return <div className={styles.success}>{children}</div>
}
