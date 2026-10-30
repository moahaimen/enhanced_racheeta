import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import type { ProviderCard as ProviderCardData } from '../../../api'
import { useLocalizedName, useScriptText } from '../../../i18n/localized'
import { Icon, type IconName } from '../../icons'
import { Avatar } from '../Avatar/Avatar'
import { PersonPlaceholder } from '../Avatar/PersonPlaceholder'
import { PROVIDER_TYPE_ICON } from '../ProviderCard/providerTypeIcon'
import type { Accent } from '../Tiles/Tiles'
import styles from './Cards.module.css'

/**
 * Showcase card for a verified provider (homepage). Real API fields only: image (when the profile
 * has one, otherwise the type icon), name, first specialty or type, rating when reviews exist,
 * location, and a booking call-to-action that opens the profile (where booking lives).
 */
export function FeaturedProviderCard({ provider }: { provider: ProviderCardData }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const text = useScriptText()
  const specialty = provider.specialties[0]
  const practitioner = provider.kind === 'PRACTITIONER'
  const rated = provider.review_count > 0 && provider.average_rating !== null
  return (
    <article className={styles.provider}>
      <Avatar
        src={provider.image_url || null}
        name={provider.display_name}
        size="xl"
        className={styles.providerAvatar}
        fallback={practitioner ? <PersonPlaceholder seed={provider.id} size={96} /> : <Icon name={PROVIDER_TYPE_ICON[provider.provider_type]} size={34} />}
      />
      <h3 className={styles.providerName}>
        <Link to={`/providers/${provider.id}`} className={styles.stretch}>
          {text(provider.display_name)}
        </Link>
      </h3>
      <p className={styles.providerRole}>{specialty ? name(specialty) : t(`providerTypes.${provider.provider_type}`)}</p>
      <p className={styles.ratingEmpty}>
        <Icon name="shieldCheck" size={14} /> {t('verification.VERIFIED')}
      </p>
      {rated ? (
        <p className={styles.rating} aria-label={t('reviews.count', { count: provider.review_count })}>
          <span aria-hidden="true">★</span> {provider.average_rating!.toFixed(1)}
          <span className={styles.ratingCount}>({provider.review_count})</span>
        </p>
      ) : null}
      <p className={styles.place}>
        <Icon name="mapPin" size={14} />
        {name(provider.governorate)}
      </p>
      <span className={styles.ctaRow} aria-hidden="true">
        <span className={styles.profileCta}>{t('providers.viewProfile')}</span>
        {practitioner ? (
          <span className={styles.bookCta}>
            <Icon name="calendar" size={14} />
            {t('home.bookNow')}
          </span>
        ) : null}
      </span>
    </article>
  )
}

/** Property card: soft-teal art header (type icon), badges, location, area and price (pre-formatted by the caller). */
export function PropertyCard({
  to,
  title,
  badges,
  location,
  area,
  price,
  accent = 'teal',
}: {
  to: string
  title: string
  badges: ReactNode
  location: string
  area?: string
  price: string
  accent?: Accent
}) {
  const text = useScriptText()
  return (
    <article className={styles.property} data-accent={accent}>
      <div className={styles.propertyArt} aria-hidden="true">
        <Icon name="building" size={44} />
      </div>
      <div className={styles.propertyBody}>
        <div className={styles.badges}>{badges}</div>
        <h3 className={styles.propertyTitle}>
          <Link to={to} className={styles.stretch}>
            {text(title)}
          </Link>
        </h3>
        <p className={styles.place}>
          <Icon name="mapPin" size={14} />
          {location}
        </p>
        <p className={styles.facts}>
          <bdi>{price}</bdi>
          {area ? <bdi className={styles.area}>{area}</bdi> : null}
        </p>
      </div>
    </article>
  )
}

/** Product card for the providers-only targeted catalogue (no cart, no checkout). */
export function ProductTile({
  to,
  title,
  company,
  category,
  price,
  icon = 'cart',
}: {
  to: string
  title: string
  company: string
  category: string
  price: string
  icon?: IconName
}) {
  const text = useScriptText()
  return (
    <article className={styles.product} data-accent="blue">
      <div className={styles.productArt} aria-hidden="true">
        <Icon name={icon} size={36} />
      </div>
      <p className={styles.productCategory}>{category}</p>
      <h3 className={styles.productTitle}>
        <Link to={to} className={styles.stretch}>
          {text(title)}
        </Link>
      </h3>
      <p className={styles.productCompany}>
        <Icon name="building" size={14} />
        {text(company)}
      </p>
      <p className={styles.productPrice} dir="auto">
        {price}
      </p>
    </article>
  )
}
