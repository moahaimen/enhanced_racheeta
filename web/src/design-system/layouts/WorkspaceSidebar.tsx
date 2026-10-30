import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router'

import { useAuth } from '../../auth/useAuth'
import { Icon, type IconName } from '../icons'
import styles from './WorkspaceSidebar.module.css'

type Item = { to: string; icon: IconName; label: string; end?: boolean }

/** Paths that live inside the signed-in workspace (persistent light sidebar). */
const WORKSPACE_PREFIXES = [
  '/dashboard',
  '/profile',
  '/notifications',
  '/messages',
  '/reservations',
  '/provider/',
  '/marketplace',
  '/company',
  '/employer',
  '/admin-console',
  '/real-estate/owner',
  '/jobs/profile',
  '/jobs/my-applications',
]

export function isWorkspacePath(pathname: string): boolean {
  return WORKSPACE_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(prefix.endsWith('/') ? prefix : `${prefix}/`) || (prefix.endsWith('/') && pathname === prefix.slice(0, -1)))
}

/** Persistent light sidebar of the signed-in workspace: one place for every account destination. */
export function WorkspaceSidebar() {
  const { t } = useTranslation()
  const { account } = useAuth()
  if (!account) return null
  const role = account.role
  const items: Item[] = [{ to: '/dashboard', icon: 'chart', label: t('nav.dashboard') }]
  if (role === 'PATIENT') items.push({ to: '/reservations', icon: 'calendar', label: t('nav.myReservations') })
  if (role === 'PROVIDER') {
    items.push(
      { to: '/provider/profile', icon: 'briefcase', label: t('nav.providerProfile') },
      { to: '/provider/reservations', icon: 'calendar', label: t('nav.providerReservations') },
      { to: '/provider/offers', icon: 'tag', label: t('nav.providerOffers') },
      { to: '/marketplace', icon: 'cart', label: t('nav.marketplace') },
    )
  }
  if (role === 'REAL_ESTATE_SELLER') items.push({ to: '/real-estate/owner', icon: 'home', label: t('nav.realEstateWorkspace') })
  if (role === 'MEDICAL_COMPANY') {
    items.push({ to: '/company', icon: 'cart', label: t('nav.companyWorkspace'), end: true }, { to: '/company/advertising', icon: 'tag', label: t('nav.advertising') })
  }
  items.push({ to: '/employer', icon: 'hospital', label: t('nav.employer') })
  items.push({ to: '/jobs/profile', icon: 'user', label: t('nav.seekerProfile') }, { to: '/jobs/my-applications', icon: 'briefcase', label: t('nav.myApplications') })
  items.push({ to: '/messages', icon: 'mail', label: t('nav.messages') }, { to: '/notifications', icon: 'bell', label: t('nav.notifications') })
  if (account.is_staff) items.push({ to: '/admin-console', icon: 'shieldCheck', label: t('nav.adminConsole') })
  items.push({ to: '/profile', icon: 'user', label: t('nav.profile') })

  return (
    <aside className={styles.sidebar} aria-label={t('nav.account')}>
      <div className={styles.who}>
        <span className={styles.avatar} aria-hidden="true">
          <Icon name="user" size={20} />
        </span>
        <div>
          <strong>{account.full_name}</strong>
          <span>{t(`roles.${account.role}`)}</span>
        </div>
      </div>
      <nav className={styles.nav} aria-label={t('nav.account')}>
        {items.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end ?? false} className={styles.link}>
            <Icon name={item.icon} size={18} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
