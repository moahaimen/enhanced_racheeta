import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, useLocation, useNavigate } from 'react-router'

import { useAuth } from '../../auth/useAuth'
import { SUPPORTED_LANGUAGES, changeLanguage, isLanguage } from '../../i18n'
import { Icon } from '../icons'
import { ApiActionButton } from '../components/Button/ApiActionButton'
import { IconButton, LinkButton } from '../components/Button/Button'
import { Container } from './Container'
import styles from './SiteHeader.module.css'

const LANGUAGE_LABELS: Record<string, string> = { ar: 'العربية', en: 'English' }

export function BrandMark({ className = '' }: { className?: string }) {
  const { t } = useTranslation()
  return (
    <NavLink to="/" className={`${styles.brand} ${className}`.trim()} aria-label={t('app.name')}>
      <span className={styles.mark} aria-hidden="true">
        <Icon name="heartPulse" size={20} />
      </span>
      <span>{t('app.name')}</span>
    </NavLink>
  )
}

function LanguageSelect() {
  const { i18n, t } = useTranslation()
  return (
    <label className={styles.lang}>
      <Icon name="globe" size={18} />
      <span className="visually-hidden">{t('common.language')}</span>
      <select
        value={i18n.language}
        onChange={(event) => {
          const next = event.target.value
          if (isLanguage(next)) void changeLanguage(next)
        }}
      >
        {SUPPORTED_LANGUAGES.map((code) => (
          <option key={code} value={code}>
            {LANGUAGE_LABELS[code]}
          </option>
        ))}
      </select>
    </label>
  )
}

/** Premium application header: brand, primary navigation, session actions, language, mobile panel. */
export function SiteHeader() {
  const { t } = useTranslation()
  const { status, account, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  // The panel is "open for this path"; navigating closes it without an effect.
  const [openAt, setOpenAt] = useState<string | null>(null)
  const open = openAt === location.pathname
  const setOpen = (next: boolean) => setOpenAt(next ? location.pathname : null)

  const links: ReactNode = (
    <>
      <NavLink to="/" end className={styles.link}>
        <Icon name="home" size={18} />
        {t('nav.home')}
      </NavLink>
      <NavLink to="/providers" className={styles.link}>
        <Icon name="search" size={18} />
        {t('nav.providers')}
      </NavLink>
      {status === 'authenticated' && account?.role === 'PROVIDER' ? (
        <NavLink to="/provider/profile" className={styles.link}>
          <Icon name="briefcase" size={18} />
          {t('nav.providerProfile')}
        </NavLink>
      ) : null}
      {status === 'authenticated' ? (
        <NavLink to="/profile" className={styles.link}>
          <Icon name="user" size={18} />
          {t('nav.profile')}
        </NavLink>
      ) : null}
    </>
  )

  const session: ReactNode =
    status === 'authenticated' ? (
      <ApiActionButton
        variant="ghost"
        action={logout}
        onSuccess={() => navigate('/login', { replace: true })}
        pendingLabel={t('nav.loggingOut')}
        leading={<Icon name="logout" size={18} />}
      >
        {t('nav.logout')}
      </ApiActionButton>
    ) : status === 'anonymous' ? (
      <>
        <LinkButton to="/login" variant="ghost">
          {t('nav.login')}
        </LinkButton>
        <LinkButton to="/register">{t('nav.register')}</LinkButton>
      </>
    ) : null

  return (
    <header className={styles.header}>
      <Container width="xl">
        <div className={styles.bar}>
          <BrandMark />
          <nav className={styles.nav} aria-label={t('nav.main')}>
            {links}
          </nav>
          <span className={styles.spacer} />
          <div className={styles.actions}>
            <LanguageSelect />
            {session}
          </div>
          <IconButton
            className={styles.menuButton}
            label={open ? t('nav.closeMenu') : t('nav.openMenu')}
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpen(!open)}
          >
            <Icon name={open ? 'x' : 'menu'} size={22} />
          </IconButton>
        </div>
        {open ? (
          <nav id="mobile-nav" className={styles.mobilePanel} aria-label={t('nav.main')}>
            {links}
            <div className={styles.mobileActions}>
              <LanguageSelect />
              {session}
            </div>
          </nav>
        ) : null}
      </Container>
    </header>
  )
}
