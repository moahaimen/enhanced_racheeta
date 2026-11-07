import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useAuth } from '../../auth/useAuth'
import { useFeatures } from '../../hooks/useFeatures'
import { Badge } from '../components/Badge/Badge'
import { Container } from './Container'
import { BrandMark } from './SiteHeader'
import styles from './SiteFooter.module.css'

/**
 * The services column only lists live modules, each linked where this visitor can actually use it:
 * - the store is public;
 * - offers are published on provider profiles (a provider manages its own);
 * - the B2B marketplace is for verified providers (buyers) and companies (sellers); everyone else
 *   sees who it is for instead of a link that would end on a refusal.
 */
export function SiteFooter() {
  const { t } = useTranslation()
  const { status, account } = useAuth()
  const { reservationsEnabled: bookingOn } = useFeatures()
  const isProvider = account?.role === 'PROVIDER'
  const isCompany = account?.role === 'MEDICAL_COMPANY'
  const marketplaceLink = isProvider ? '/marketplace' : isCompany ? '/company' : null
  return (
    <footer className={styles.footer} data-testid="site-footer">
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
              <li>
                <Link to="/jobs">{t('nav.jobs')}</Link>
              </li>
              <li>
                <Link to="/real-estate">{t('modules.realEstate')}</Link>
              </li>
              {bookingOn ? (
                <li>
                  <Link to="/providers">{t('modules.reservations')}</Link>
                </li>
              ) : null}
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
            <h2 className={styles.colTitle}>{t('footer.services')}</h2>
            <ul className={styles.list} data-testid="footer-services">
              <li>
                <Link to="/store">{t('nav.store')}</Link>
              </li>
              <li>
                {isProvider ? (
                  <Link to="/provider/offers">{t('footer.manageOffers')}</Link>
                ) : (
                  <Link to="/providers">{t('footer.offersOnProfiles')}</Link>
                )}
              </li>
              <li className={marketplaceLink ? undefined : styles.restricted}>
                {marketplaceLink ? (
                  <Link to={marketplaceLink}>{t('modules.marketplace')}</Link>
                ) : (
                  <>
                    <span>{t('modules.marketplace')}</span>
                    <Badge tone="outline">{t('footer.forProfessionals')}</Badge>
                  </>
                )}
              </li>
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
