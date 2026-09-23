import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useNavigate } from 'react-router'

import { useAuth } from '../auth/useAuth'
import { ApiActionButton } from '../components/ApiActionButton'
import { LanguageSwitcher } from '../components/LanguageSwitcher'

export function AppLayout() {
  const { t } = useTranslation()
  const { status, account, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="app">
      <header className="app__header">
        <div>
          <h1 className="app__title">
            <NavLink to="/" className="app__brand">
              {t('app.name')}
            </NavLink>
          </h1>
          <p className="app__tagline">{t('app.tagline')}</p>
        </div>
        <nav className="app__nav" aria-label="main">
          <NavLink to="/">{t('nav.home')}</NavLink>
          {status === 'authenticated' ? (
            <>
              <NavLink to="/profile">{t('nav.profile')}</NavLink>
              <ApiActionButton
                className="btn--ghost"
                action={logout}
                onSuccess={() => navigate('/login', { replace: true })}
                pendingLabel={t('nav.loggingOut')}
                aria-label={t('nav.logout')}
              >
                {t('nav.logout')}
                {account ? <span className="visually-hidden"> ({account.email})</span> : null}
              </ApiActionButton>
            </>
          ) : status === 'anonymous' ? (
            <>
              <NavLink to="/login">{t('nav.login')}</NavLink>
              <NavLink to="/register">{t('nav.register')}</NavLink>
            </>
          ) : null}
          <LanguageSwitcher />
        </nav>
      </header>
      <main className="app__main">
        <Outlet />
      </main>
    </div>
  )
}
