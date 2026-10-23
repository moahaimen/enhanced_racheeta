import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, useLocation, useNavigate } from 'react-router'

import { useAuth } from '../../auth/useAuth'
import { useChat } from '../../chat/useChat'
import { useNotifications } from '../../notifications/useNotifications'
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

const BADGE_CAP = 99

/**
 * Bell entry with the backend-reported unread count (hidden at 0, capped at 99+). `compact` is the
 * icon-only desktop form (the text stays available to assistive technology); the mobile panel
 * shows the label.
 */
function NotificationsLink({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation()
  const { unreadCount } = useNotifications()
  const count = unreadCount ?? 0
  return (
    <NavLink to="/notifications" className={compact ? styles.iconLink : styles.link}>
      <Icon name="bell" size={compact ? 20 : 18} />
      <span className={compact ? 'visually-hidden' : undefined}>{t('nav.notifications')}</span>
      {count > 0 ? (
        <span
          className={styles.badge}
          data-testid="notifications-badge"
          aria-label={t('notifications.unreadLabel', { count })}
        >
          {count > BADGE_CAP ? `${BADGE_CAP}+` : count}
        </span>
      ) : null}
    </NavLink>
  )
}

function MessagesLink({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation()
  const { unreadCount } = useChat()
  const count = unreadCount ?? 0
  return (
    <NavLink to="/messages" className={compact ? styles.iconLink : styles.link}>
      <Icon name="mail" size={compact ? 20 : 18} />
      <span className={compact ? 'visually-hidden' : undefined}>{t('nav.messages')}</span>
      {count > 0 ? (
        <span
          className={styles.badge}
          data-testid="messages-badge"
          aria-label={t('messages.unreadLabel', { count })}
        >
          {count > BADGE_CAP ? `${BADGE_CAP}+` : count}
        </span>
      ) : null}
    </NavLink>
  )
}

/**
 * Desktop account/workspace disclosure: every account-specific destination lives here instead of
 * crowding the bar. A plain disclosure (button + panel of ordinary links): Tab moves through the
 * links, Escape closes and returns focus to the button, a click outside or a navigation closes it.
 * The panel is hidden with CSS only, so it never takes space or focus while closed.
 */
function AccountMenu({ children, name, role }: { children: ReactNode; name: string; role: string }) {
  const { t } = useTranslation()
  const location = useLocation()
  const panelId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const [openAt, setOpenAt] = useState<string | null>(null)
  const open = openAt === location.key
  const setOpen = (next: boolean) => setOpenAt(next ? location.key : null)

  useEffect(() => {
    if (!open) return
    const onPointer = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpenAt(null)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpenAt(null)
        buttonRef.current?.focus()
      }
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className={styles.account} ref={rootRef}>
      <button
        ref={buttonRef}
        type="button"
        className={styles.accountButton}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(!open)}
      >
        <span className={styles.avatar} aria-hidden="true">
          <Icon name="user" size={16} />
        </span>
        <span>{t('nav.account')}</span>
        <Icon name="chevronDown" size={16} />
      </button>
      <div id={panelId} className={styles.accountPanel} data-open={open} role="group" aria-label={t('nav.account')}>
        <div className={styles.accountHead}>
          <strong>{name}</strong>
          <span>{role}</span>
        </div>
        {children}
      </div>
    </div>
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
  // The facilities shortcut is the same page with ?kind=FACILITY: NavLink ignores the query, so the
  // two entries decide their own active state.
  const onProviders = location.pathname === '/providers'
  const onFacilities = new URLSearchParams(location.search).get('kind') === 'FACILITY'
  const authenticated = status === 'authenticated'

  /** Public navigation: the same for everyone, always visible on desktop. */
  const publicLinks: ReactNode = (
    <>
      <NavLink to="/" end className={styles.link}>
        <Icon name="home" size={18} />
        {t('nav.home')}
      </NavLink>
      <Link to="/providers" className={styles.link} aria-current={onProviders && !onFacilities ? 'page' : undefined}>
        <Icon name="search" size={18} />
        {t('nav.providers')}
      </Link>
      <Link to="/providers?kind=FACILITY" className={styles.link} aria-current={onProviders && onFacilities ? 'page' : undefined}>
        <Icon name="hospital" size={18} />
        {t('nav.facilities')}
      </Link>
      <NavLink to="/jobs" className={styles.link}>
        <Icon name="briefcase" size={18} />
        {t('nav.jobs')}
      </NavLink>
      <NavLink to="/real-estate" end className={styles.link}>
        <Icon name="building" size={18} />
        {t('nav.realEstate')}
      </NavLink>
    </>
  )

  /** Account- and role-specific destinations: desktop account menu, mobile panel. */
  const accountLinks: ReactNode = authenticated ? (
    <>
      <NavLink to="/dashboard" className={styles.link}>
        <Icon name="chart" size={18} />
        {t('nav.dashboard')}
      </NavLink>
      {account?.role === 'PATIENT' ? (
        <NavLink to="/reservations" className={styles.link}>
          <Icon name="calendar" size={18} />
          {t('nav.myReservations')}
        </NavLink>
      ) : null}
      {account?.role === 'PROVIDER' ? (
        <>
          <NavLink to="/provider/profile" className={styles.link}>
            <Icon name="briefcase" size={18} />
            {t('nav.providerProfile')}
          </NavLink>
          <NavLink to="/provider/reservations" className={styles.link}>
            <Icon name="calendar" size={18} />
            {t('nav.providerReservations')}
          </NavLink>
          <NavLink to="/provider/offers" className={styles.link}>
            <Icon name="tag" size={18} />
            {t('nav.providerOffers')}
          </NavLink>
          <NavLink to="/marketplace" className={styles.link}>
            <Icon name="cart" size={18} />
            {t('nav.marketplace')}
          </NavLink>
        </>
      ) : null}
      {account?.role === 'REAL_ESTATE_SELLER' ? (
        <NavLink to="/real-estate/owner" className={styles.link}>
          <Icon name="home" size={18} />
          {t('nav.realEstateWorkspace')}
        </NavLink>
      ) : null}
      {account?.role === 'MEDICAL_COMPANY' ? (
        <>
          <NavLink to="/company" end className={styles.link}>
            <Icon name="cart" size={18} />
            {t('nav.companyWorkspace')}
          </NavLink>
          <NavLink to="/company/advertising" className={styles.link}>
            <Icon name="tag" size={18} />
            {t('nav.advertising')}
          </NavLink>
        </>
      ) : null}
      <NavLink to="/employer" className={styles.link}>
        <Icon name="hospital" size={18} />
        {t('nav.employer')}
      </NavLink>
      {account?.is_staff ? (
        <NavLink to="/admin-console" className={styles.link}>
          <Icon name="shieldCheck" size={18} />
          {t('nav.adminConsole')}
        </NavLink>
      ) : null}
      <NavLink to="/profile" className={styles.link}>
        <Icon name="user" size={18} />
        {t('nav.profile')}
      </NavLink>
    </>
  ) : null

  const logoutButton: ReactNode = (
    <ApiActionButton
      variant="ghost"
      action={logout}
      onSuccess={() => navigate('/login', { replace: true })}
      pendingLabel={t('nav.loggingOut')}
      leading={<Icon name="logout" size={18} />}
    >
      {t('nav.logout')}
    </ApiActionButton>
  )

  const guestActions: ReactNode =
    status === 'anonymous' ? (
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
            {publicLinks}
          </nav>
          <span className={styles.spacer} />
          <div className={styles.actions}>
            {authenticated ? (
              <>
                <MessagesLink compact />
                <NotificationsLink compact />
                <AccountMenu name={account?.full_name ?? ''} role={account ? t(`roles.${account.role}`) : ''}>
                  <div className={styles.accountLinks}>{accountLinks}</div>
                  <div className={styles.accountFoot}>{logoutButton}</div>
                </AccountMenu>
              </>
            ) : null}
            <LanguageSelect />
            {guestActions}
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
            {publicLinks}
            {accountLinks}
            {authenticated ? <MessagesLink /> : null}
            {authenticated ? <NotificationsLink /> : null}
            <div className={styles.mobileActions}>
              <LanguageSelect />
              {authenticated ? logoutButton : guestActions}
            </div>
          </nav>
        ) : null}
      </Container>
    </header>
  )
}
