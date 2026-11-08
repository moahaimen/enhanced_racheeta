import { useTranslation } from 'react-i18next'
import { Outlet } from 'react-router'

import { ApiError, providers as providersApi } from '../api'
import { useAuth } from '../auth/useAuth'
import { Container, EmptyState, ErrorState, LinkButton, LoadingState } from '../design-system'
import { useAsyncData } from '../hooks/useAsync'

/**
 * Provider pages that need a provider profile (and, for the professional catalogue and quotes, a
 * VERIFIED one). Instead of letting each page fail with the server's refusal, this explains the next
 * step and links to it. It never grants anything: the backend still enforces every rule.
 */
export function RequireProviderProfile({ verified = false }: { verified?: boolean }) {
  const { account } = useAuth()
  return <Gate key={account?.id ?? 'anonymous'} verified={verified} />
}

function Gate({ verified }: { verified: boolean }) {
  const { t } = useTranslation()
  const profile = useAsyncData((signal) => providersApi.getMyProvider(signal), [])
  if (profile.loading) return <LoadingState />
  if (profile.error instanceof ApiError && profile.error.status === 404) {
    return (
      <Container width="lg">
        <div className="card-block" data-testid="provider-profile-required">
          <EmptyState
            icon="stethoscope"
            title={t('gate.noProfileTitle')}
            action={<LinkButton to="/provider/profile">{t('gate.createProfile')}</LinkButton>}
          >
            {t('gate.noProfileHint')}
          </EmptyState>
        </div>
      </Container>
    )
  }
  if (profile.error) {
    return <ErrorState title={t('errors.generic', { defaultValue: '' })} error={profile.error} onRetry={profile.reload} />
  }
  if (verified && profile.data && profile.data.verification_status !== 'VERIFIED') {
    return (
      <Container width="lg">
        <div className="card-block" data-testid="provider-verification-required">
          <EmptyState
            icon="shieldCheck"
            title={t('gate.notVerifiedTitle')}
            action={<LinkButton to="/provider/profile">{t('gate.openProfile')}</LinkButton>}
          >
            {t('gate.notVerifiedHint', { status: t(`verification.${profile.data.verification_status}`) })}
          </EmptyState>
        </div>
      </Container>
    )
  }
  return <Outlet />
}
