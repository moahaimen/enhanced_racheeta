import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

export function NotFoundPage() {
  const { t } = useTranslation()
  return (
    <section className="card" role="alert">
      <h2>{t('notFound.title')}</h2>
      <p>{t('notFound.body')}</p>
      <Link to="/" className="btn">
        {t('notFound.home')}
      </Link>
    </section>
  )
}
