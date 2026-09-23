import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { health } from '../api'
import { ApiActionButton, AsyncPage } from '../components'

/**
 * Phase 0 demonstration page: loads /health/ through AsyncPage and re-checks
 * it through ApiActionButton. Both patterns are mandatory for real features.
 */
export function HomePage() {
  const { t, i18n } = useTranslation()
  const [lastChecked, setLastChecked] = useState<Date | null>(null)

  return (
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
  )
}
