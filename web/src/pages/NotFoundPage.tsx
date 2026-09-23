import { useTranslation } from 'react-i18next'

import { Container, EmptyState, LinkButton } from '../design-system'

export function NotFoundPage() {
  const { t } = useTranslation()
  return (
    <Container width="md">
      <div className="card-block" role="alert">
        <EmptyState icon="alertCircle" title={t('notFound.title')} action={<LinkButton to="/">{t('notFound.home')}</LinkButton>}>
          {t('notFound.body')}
        </EmptyState>
      </div>
    </Container>
  )
}
