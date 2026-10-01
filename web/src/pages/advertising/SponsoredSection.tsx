import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { advertising as advertisingApi } from '../../api'
import type { PaginatedSponsored, SponsoredCampaign } from '../../api'
import { Alert, ApiActionButton, Badge, ErrorState, Icon, LoadingState, SectionCard } from '../../design-system'
import { useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'

/**
 * Sponsored campaigns for /marketplace. The BACKEND returns only the advertisements this provider is
 * eligible for (product targeting AND campaign narrowing AND payment/date state); nothing is filtered
 * here. A failure stays inside this section, so the organic catalogue keeps working, and an empty
 * result renders nothing. Every card carries the "Sponsored" label — ads are never disguised as organic.
 *
 * The backend paginates (20 per page). Page 1 loads first; while it reports a `next` page, a "Load more"
 * control appends the following page in the backend's order, so every paid campaign stays reachable. The
 * browser only pages through what the backend already authorised: no filtering, ranking or page cap.
 */
export function SponsoredSection() {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const ads = useAsyncData((signal) => advertisingApi.listSponsored(1, signal), [])
  // Pages after the first. Loading one never replaces what is already rendered.
  const [more, setMore] = useState<{ ads: SponsoredCampaign[]; next: string | null; page: number } | null>(null)
  const [moreError, setMoreError] = useState(false)
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), []) // unmounting aborts an in-flight page request

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
  const first = ads.data?.results ?? []
  if (first.length === 0) return null
  const results = [...first, ...(more?.ads ?? [])]
  const next = more ? more.next : (ads.data?.next ?? null)
  const nextPage = (more?.page ?? 1) + 1
  const loadMore = () => {
    controller.current?.abort()
    controller.current = new AbortController()
    return advertisingApi.listSponsored(nextPage, controller.current.signal)
  }
  const append = (res: PaginatedSponsored) => {
    setMoreError(false)
    setMore((prev) => {
      const seen = new Set([...first, ...(prev?.ads ?? [])].map((a) => a.id)) // defensive: never render an ad twice
      return { ads: [...(prev?.ads ?? []), ...res.results.filter((a) => !seen.has(a.id))], next: res.next, page: nextPage }
    })
  }

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
      {moreError ? (
        <Alert kind="error">
          <span data-testid="sponsored-more-error">{t('advertising.sponsoredMoreError')}</span>
        </Alert>
      ) : null}
      {next ? (
        // Disabled while the next page loads (ApiActionButton): no concurrent or duplicate page requests.
        <ApiActionButton variant="secondary" action={loadMore} onSuccess={append} onError={() => setMoreError(true)} pendingLabel={t('advertising.loadingMoreSponsored')}>
          {t('advertising.loadMoreSponsored')}
        </ApiActionButton>
      ) : null}
    </SectionCard>
  )
}
