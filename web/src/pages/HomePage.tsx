import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { health } from '../api'
import { useAuth } from '../auth/useAuth'
import { ApiActionButton, AsyncPage } from '../components'

export function HomePage() {
  const { t, i18n } = useTranslation()
  const { status, account } = useAuth()
  const [lastChecked, setLastChecked] = useState<Date | null>(null)

  return (
    <>
      <section className="card">
        {status === 'authenticated' && account ? (
          <>
            <h2>{t('home.welcome', { name: account.full_name })}</h2>
            <Link className="btn" to="/profile">
              {t('home.goToProfile')}
            </Link>
          </>
        ) : (
          <>
            <h2>{t('app.tagline')}</h2>
            <p>{t('home.intro')}</p>
            <div className="actions">
              <Link className="btn" to="/login">
                {t('nav.login')}
              </Link>
              <Link className="btn btn--ghost" to="/register">
                {t('nav.register')}
              </Link>
            </div>
          </>
        )}
      </section>
      <section className="card">
        <h2>{t('home.title')}</h2>
        <AsyncPage load={(signal) => health.getHealth(signal)}>
          {(data, reload) => (
            <>
              <dl className="status">
                <dt>{t('home.apiStatus')}</dt>
                <dd>
                  <span className={`badge badge--${data.status}`}>{t('home.ok')}</span>
                </dd>
                {lastChecked && (
                  <>
                    <dt>{t('home.lastChecked')}</dt>
                    <dd>{lastChecked.toLocaleTimeString(i18n.language)}</dd>
                  </>
                )}
              </dl>
              <ApiActionButton
                action={() => health.getHealth()}
                onSuccess={() => {
                  setLastChecked(new Date())
                  reload()
                }}
                pendingLabel={t('home.checking')}
              >
                {t('home.checkAgain')}
              </ApiActionButton>
            </>
          )}
        </AsyncPage>
      </section>
    </>
  )
}
