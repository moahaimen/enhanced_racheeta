import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { advertising as advertisingApi } from '../../api'
import { Badge, ErrorState, Icon, LoadingState, SectionCard } from '../../design-system'
import { useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'

/**
 * Sponsored campaigns for /marketplace. The BACKEND returns only the advertisements this provider is
 * eligible for (product targeting AND campaign narrowing AND payment/date state); nothing is filtered
 * here. A failure stays inside this section, so the organic catalogue keeps working, and an empty
 * result renders nothing. Every card carries the "Sponsored" label — ads are never disguised as organic.
 */
export function SponsoredSection() {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const ads = useAsyncData((signal) => advertisingApi.listSponsored(1, signal), [])

  if (ads.loading) {
    return (
      <SectionCard title={t('advertising.sponsoredSection')} headingLevel={2}>
        <LoadingState testId="sponsored-loading" />
      </SectionCard>
    )
  }
  if (ads.error) {
    return (
      <SectionCard title={t('advertising.sponsoredSection')} headingLevel={2}>
        <div data-testid="sponsored-error">
          <ErrorState title={t('advertising.sponsoredError')} error={ads.error} onRetry={ads.reload} />
        </div>
      </SectionCard>
    )
  }
  const results = ads.data?.results ?? []
  if (results.length === 0) return null

  return (
    <SectionCard title={t('advertising.sponsoredSection')} description={t('advertising.sponsoredIntro')} headingLevel={2}>
      <ul className="stack" data-testid="sponsored-results" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {results.map((ad) => (
          <li key={ad.id} className="card-block" data-testid="sponsored-ad">
            <div className="cluster">
              <Badge tone="warning">
                <Icon name="tag" size={12} /> {t('advertising.sponsored')}
              </Badge>
              <Link to={`/marketplace/products/${ad.product.id}`}>
                <strong>{ad.product.title}</strong>
              </Link>
              <Badge tone="brand">{name(ad.product.category)}</Badge>
            </div>
            <div className="text-caption">
              {ad.product.company.name}
              {ad.product.brand ? ` · ${ad.product.brand}` : ''}
              {ad.product.model_name ? ` · ${ad.product.model_name}` : ''}
            </div>
            <div className="text-secondary" dir="auto">
              {ad.product.price === null ? t('marketplace.priceOnRequest') : `${Number(ad.product.price).toLocaleString(i18n.language)} ${ad.product.currency}`}
            </div>
          </li>
        ))}
      </ul>
    </SectionCard>
  )
}
