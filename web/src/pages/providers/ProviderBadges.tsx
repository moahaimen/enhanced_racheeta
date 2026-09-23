import { useTranslation } from 'react-i18next'

import type { ProviderType, VerificationStatus } from '../../api'
import { Badge, Icon } from '../../design-system'

export function ProviderTypeBadge({ type }: { type: ProviderType }) {
  const { t } = useTranslation()
  return <Badge tone="brand">{t(`providerTypes.${type}`)}</Badge>
}

const TONE: Record<VerificationStatus, 'success' | 'warning' | 'error' | 'neutral'> = {
  VERIFIED: 'success',
  PENDING: 'warning',
  REJECTED: 'error',
  SUSPENDED: 'error',
  UNVERIFIED: 'neutral',
}

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  const { t } = useTranslation()
  return (
    <Badge tone={TONE[status]} leading={status === 'VERIFIED' ? <Icon name="shieldCheck" size={12} /> : undefined}>
      {t(`verification.${status}`)}
    </Badge>
  )
}
