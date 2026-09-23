import { useTranslation } from 'react-i18next'

import { LanguageSwitcher } from './components'
import { HomePage } from './pages/HomePage'

export default function App() {
  const { t } = useTranslation()
  return (
    <div className="app">
      <header className="app__header">
        <div>
          <h1 className="app__title">{t('app.name')}</h1>
          <p className="app__tagline">{t('app.tagline')}</p>
        </div>
        <LanguageSwitcher />
      </header>
      <main className="app__main">
        <HomePage />
      </main>
    </div>
  )
}
