import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useAuth } from '../../auth/useAuth'
import { Badge } from '../components/Badge/Badge'
import { Container } from './Container'
import { BrandMark } from './SiteHeader'
import styles from './SiteFooter.module.css'

const UPCOMING = ['reservations', 'offers', 'jobs', 'marketplace', 'realEstate'] as const

export function SiteFooter() {
  const { t } = useTranslation()
  const { status } = useAuth()
  return (
    <footer className={styles.footer}>
      <Container width="xl">
        <div className={styles.grid}>
          <div>
            <BrandMark />
            <p className={styles.tagline}>{t('footer.tagline')}</p>
          </div>
          <div>
            <h2 className={styles.colTitle}>{t('footer.platform')}</h2>
            <ul className={styles.list}>
              <li>
                <Link to="/">{t('nav.home')}</Link>
              </li>
              <li>
                <Link to="/providers">{t('nav.providers')}</Link>
              </li>
              {status === 'authenticated' ? (
                <li>
                  <Link to="/profile">{t('nav.profile')}</Link>
                </li>
              ) : (
                <>
                  <li>
                    <Link to="/login">{t('nav.login')}</Link>
                  </li>
                  <li>
                    <Link to="/register">{t('nav.register')}</Link>
                  </li>
                </>
              )}
            </ul>
          </div>
          <div>
            <h2 className={styles.colTitle}>{t('footer.upcoming')}</h2>
            <ul className={styles.list}>
              {UPCOMING.map((key) => (
                <li key={key} className={styles.upcoming}>
                  <span>{t(`modules.${key}`)}</span>
                  <Badge tone="outline">{t('common.soon')}</Badge>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <div className={styles.bottom}>
          <span>{t('footer.rights', { year: new Date().getFullYear() })}</span>
          <span>{t('app.tagline')}</span>
        </div>
      </Container>
    </footer>
  )
}
