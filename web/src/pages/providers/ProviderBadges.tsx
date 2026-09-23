import { useTranslation } from 'react-i18next'

import type { ProviderType, VerificationStatus } from '../../api'

export function ProviderTypeBadge({ type }: { type: ProviderType }) {
  const { t } = useTranslation()
  return <span className="badge">{t(`providerTypes.${type}`)}</span>
}

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  const { t } = useTranslation()
  const tone = status === 'VERIFIED' ? 'ok' : status === 'PENDING' ? 'warn' : 'muted'
  return <span className={`badge badge--${tone}`}>{t(`verification.${status}`)}</span>
}
