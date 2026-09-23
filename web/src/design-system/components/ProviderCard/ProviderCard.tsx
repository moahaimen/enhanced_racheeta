import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import type { ProviderCard as ProviderCardData } from '../../../api'
import { useLocalizedName } from '../../../i18n/localized'
import { Icon } from '../../icons'
import { Avatar } from '../Avatar/Avatar'
import { Badge } from '../Badge/Badge'
import { Card } from '../Card/Card'
import { Skeleton } from '../States/States'
import styles from './ProviderCard.module.css'
import { PROVIDER_TYPE_ICON } from './providerTypeIcon'

const MAX_SPECIALTIES = 3

/**
 * The signature Racheeta provider card. Renders only fields the discovery
 * API returns. The "verified" badge is truthful: the public list contains
 * verified providers only (docs/API.md).
 */
export function ProviderCard({ provider }: { provider: ProviderCardData }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const extra = provider.specialties.length - MAX_SPECIALTIES
  return (
    <Card as="article" interactive className={styles.card} style={{ position: 'relative' }}>
      <div className={styles.top}>
        <Avatar
          src={provider.image_url || null}
          name={provider.display_name}
          size="lg"
          fallback={<Icon name={PROVIDER_TYPE_ICON[provider.provider_type]} size={28} />}
        />
        <div className={styles.identity}>
          <h3 className={styles.name}>
            <Link to={`/providers/${provider.id}`}>{provider.display_name}</Link>
          </h3>
          <div className={styles.meta}>
            <Badge tone="brand">{t(`providerTypes.${provider.provider_type}`)}</Badge>
            <Badge tone="success" leading={<Icon name="shieldCheck" size={12} />}>
              {t('verification.VERIFIED')}
            </Badge>
          </div>
        </div>
      </div>
      <span className={styles.location}>
        <Icon name="mapPin" size={16} />
        {name(provider.governorate)}
        {provider.city ? ` — ${name(provider.city)}` : ''}
      </span>
      {provider.specialties.length > 0 ? (
        <ul className={styles.chips} aria-label={t('providers.specialty')}>
          {provider.specialties.slice(0, MAX_SPECIALTIES).map((s) => (
            <li key={s.id}>
              <Badge tone="outline">{name(s)}</Badge>
            </li>
          ))}
          {extra > 0 ? (
            <li>
              <Badge tone="outline">+{extra}</Badge>
            </li>
          ) : null}
        </ul>
      ) : null}
      <div className={styles.footer}>
        <span className={styles.cta} aria-hidden="true">
          {t('providers.viewProfile')}
          <Icon name="arrowForward" size={16} flipInRtl />
        </span>
      </div>
    </Card>
  )
}

export function ProviderCardSkeleton() {
  return (
    <Card className={styles.card} aria-hidden="true">
      <div className={styles.skeletonRow}>
        <Skeleton width="4.5rem" height="4.5rem" />
        <div style={{ flex: 1 }} className="stack stack-sm">
          <Skeleton width="70%" height="1.1rem" />
          <Skeleton width="40%" height="0.9rem" />
        </div>
      </div>
      <Skeleton width="55%" height="0.9rem" />
      <Skeleton width="80%" height="1.5rem" />
    </Card>
  )
}
