import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { jobs as jobsApi, marketplace, providers as providersApi, realEstate, reference } from '../../api'
import type { ProviderCard as ProviderCardData } from '../../api'
import {
  AsyncPage,
  Badge,
  CountUp,
  EmptyState,
  FeaturedProviderCard,
  Icon,
  JobCard,
  JobCardSkeleton,
  LinkButton,
  NearViewport,
  ProductTile,
  PropertyCard,
  Reveal,
  SectionHeader,
  Skeleton,
  StatChip,
  type IconName,
} from '../../design-system'
import { useLocalizedName, useScriptText } from '../../i18n/localized'
import { formatArea, formatListingPrice } from '../realEstate/realEstateFormat'
import styles from './Home.module.css'


function ViewAll({ to, label }: { to: string; label: string }) {
  return (
    <LinkButton to={to} variant="secondary" size="sm" trailing={<Icon name="arrowForward" size={16} flipInRtl />}>
      {label}
    </LinkButton>
  )
}

function CardSkeleton() {
  return (
    <div className={styles.skeletonCard} aria-hidden="true">
      <Skeleton width="4.5rem" height="4.5rem" />
      <Skeleton width="60%" height="1rem" />
      <Skeleton width="40%" height="0.85rem" />
    </div>
  )
}

/** Rating, then review volume: the best-reviewed verified doctors of the latest page. */
function byRating(a: ProviderCardData, b: ProviderCardData): number {
  return (b.average_rating ?? 0) - (a.average_rating ?? 0) || b.review_count - a.review_count
}

export function FeaturedDoctors() {
  const { t } = useTranslation()
  return (
    <section className={styles.block} aria-labelledby="doctors-title">
      <Reveal>
        <SectionHeader title={<span id="doctors-title">{t('home.doctorsTitle')}</span>} description={t('home.doctorsBody')} actions={<ViewAll to="/providers?kind=PRACTITIONER" label={t('home.viewAll')} />} />
      </Reveal>
      <NearViewport minHeight="18rem">
        <AsyncPage
          load={(signal) => providersApi.listProviders({ kind: 'PRACTITIONER', page_size: 12 }, signal)}
          skeleton={
            <div className={styles.fourUp}>
              {Array.from({ length: 4 }, (_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          }
        >
          {(page) =>
            page.results.length === 0 ? (
              <EmptyState icon="stethoscope" title={t('home.featuredEmpty')} testId="featured-empty">
                {t('home.featuredEmptyBody')}
              </EmptyState>
            ) : (
              <div className={styles.fourUp} data-testid="featured-doctors">
                {[...page.results]
                  .sort(byRating)
                  .slice(0, 4)
                  .map((provider, index) => (
                    <Reveal key={provider.id} index={index}>
                      <FeaturedProviderCard provider={provider} />
                    </Reveal>
                  ))}
              </div>
            )
          }
        </AsyncPage>
      </NearViewport>
    </section>
  )
}

export function Facilities() {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const text = useScriptText()
  return (
    <section className={styles.block} aria-labelledby="facilities-title">
      <Reveal>
        <SectionHeader title={<span id="facilities-title">{t('home.facilitiesTitle')}</span>} description={t('home.facilitiesBody')} actions={<ViewAll to="/providers?kind=FACILITY" label={t('home.viewAll')} />} />
      </Reveal>
      <NearViewport minHeight="12rem">
        <AsyncPage
          load={(signal) => providersApi.listProviders({ kind: 'FACILITY', page_size: 6 }, signal)}
          skeleton={
            <div className={styles.threeUp}>
              {Array.from({ length: 3 }, (_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          }
        >
          {(page) =>
            page.results.length === 0 ? null : (
              <ul className={styles.facilityGrid} data-testid="facilities">
                {page.results.map((facility, index) => (
                  <Reveal as="li" key={facility.id} index={index} className={styles.facility}>
                    <span className={styles.facilityIcon} aria-hidden="true">
                      <Icon name={facility.provider_type === 'PHARMACY' ? 'pill' : facility.provider_type === 'LABORATORY' ? 'flask' : 'hospital'} size={24} />
                    </span>
                    <span className={styles.facilityText}>
                      <Link to={`/providers/${facility.id}`} className={styles.facilityName}>
                        {text(facility.display_name)}
                      </Link>
                      <span className={styles.facilityMeta}>
                        {t(`providerTypes.${facility.provider_type}`)} · {name(facility.governorate)}
                      </span>
                    </span>
                  </Reveal>
                ))}
              </ul>
            )
          }
        </AsyncPage>
      </NearViewport>
    </section>
  )
}

export function SpecialtyChips() {
  const { t } = useTranslation()
  const name = useLocalizedName()
  return (
    <NearViewport minHeight="6rem">
      <AsyncPage load={(signal) => reference.listSpecialties(signal)} skeleton={<span />}>
        {(specialties) =>
          specialties.length === 0 ? null : (
            <section className={styles.block} aria-labelledby="specialties-title">
              <Reveal>
                <SectionHeader title={<span id="specialties-title">{t('home.specialtiesTitle')}</span>} description={t('home.specialtiesBody')} />
              </Reveal>
              <Reveal>
                <ul className={styles.chips}>
                  {specialties
                    .filter((s) => s.parent === null)
                    .slice(0, 18)
                    .map((s) => (
                      <li key={s.id}>
                        <Link to={`/providers?specialty=${encodeURIComponent(s.slug)}`} className={styles.chip}>
                          {name(s)}
                        </Link>
                      </li>
                    ))}
                </ul>
              </Reveal>
            </section>
          )
        }
      </AsyncPage>
    </NearViewport>
  )
}

export function LatestJobs() {
  const { t } = useTranslation()
  return (
    <section className={styles.block} aria-labelledby="latest-jobs-title">
      <Reveal>
        <SectionHeader title={<span id="latest-jobs-title">{t('home.jobsLatestTitle')}</span>} description={t('home.jobsLatestBody')} actions={<ViewAll to="/jobs" label={t('home.viewAll')} />} />
      </Reveal>
      <NearViewport minHeight="16rem">
        <AsyncPage
          load={(signal) => jobsApi.listJobs({ page_size: 6 }, signal)}
          skeleton={
            <div className={styles.threeUp}>
              {Array.from({ length: 3 }, (_, i) => (
                <JobCardSkeleton key={i} />
              ))}
            </div>
          }
        >
          {(page) =>
            page.results.length === 0 ? (
              <EmptyState icon="briefcase" title={t('home.jobsEmpty')} />
            ) : (
              <div className={styles.threeUp} data-testid="latest-jobs">
                {page.results.slice(0, 6).map((job, index) => (
                  <Reveal key={job.id} index={index}>
                    <JobCard job={job} />
                  </Reveal>
                ))}
              </div>
            )
          }
        </AsyncPage>
      </NearViewport>
    </section>
  )
}

export function LatestProperties() {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  return (
    <section className={styles.block} aria-labelledby="estate-title">
      <Reveal>
        <SectionHeader title={<span id="estate-title">{t('home.estateTitle')}</span>} description={t('home.estateBody')} actions={<ViewAll to="/real-estate" label={t('home.estateAll')} />} />
      </Reveal>
      <NearViewport minHeight="14rem">
        <AsyncPage
          load={(signal) => realEstate.listListings({}, signal)}
          skeleton={
            <div className={styles.fourUp}>
              {Array.from({ length: 4 }, (_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          }
        >
          {(page) =>
            page.results.length === 0 ? (
              <EmptyState icon="building" title={t('home.estateEmpty')} />
            ) : (
              <div className={styles.fourUp} data-testid="latest-properties">
                {page.results.slice(0, 4).map((listing, index) => (
                  <Reveal key={listing.id} index={index}>
                    <PropertyCard
                      to={`/real-estate/${listing.id}`}
                      title={listing.title}
                      badges={
                        <>
                          <Badge tone={listing.transaction_type === 'SALE' ? 'brand' : 'success'}>{t(`transactionTypes.${listing.transaction_type}`)}</Badge>
                          <Badge tone="outline">{t(`propertyTypes.${listing.property_type}`)}</Badge>
                        </>
                      }
                      location={`${name(listing.governorate)}${listing.district ? ` · ${listing.district}` : ''}`}
                      area={listing.area_sqm !== null ? `${formatArea(listing.area_sqm, i18n.language)} ${t('realEstate.sqm')}` : undefined}
                      price={formatListingPrice(listing, i18n.language, t('realEstate.priceOnRequest'))}
                    />
                  </Reveal>
                ))}
              </div>
            )
          }
        </AsyncPage>
      </NearViewport>
    </section>
  )
}

/** Providers only: the targeted catalogue the BACKEND returns for the caller's profile. */
export function ProductsForProviders() {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  return (
    <section className={styles.block} aria-labelledby="products-title">
      <Reveal>
        <SectionHeader title={<span id="products-title">{t('home.productsTitle')}</span>} description={t('home.productsBody')} actions={<ViewAll to="/marketplace" label={t('home.productsAll')} />} />
      </Reveal>
      <NearViewport minHeight="12rem">
        <AsyncPage load={(signal) => marketplace.listTargetedProducts(1, '', signal)} skeleton={<div className={styles.fourUp}>{Array.from({ length: 4 }, (_, i) => <CardSkeleton key={i} />)}</div>}>
          {(page) =>
            page.results.length === 0 ? (
              <EmptyState icon="cart" title={t('home.productsEmpty')} />
            ) : (
              <div className={styles.fourUp} data-testid="home-products">
                {page.results.slice(0, 4).map((product, index) => (
                  <Reveal key={product.id} index={index}>
                    <ProductTile
                      to={`/marketplace/products/${product.id}`}
                      title={product.title}
                      company={product.company.name}
                      category={name(product.category)}
                      price={product.price === null ? t('home.priceOnRequest') : `${Number(product.price).toLocaleString(i18n.language)} ${product.currency}`}
                    />
                  </Reveal>
                ))}
              </div>
            )
          }
        </AsyncPage>
      </NearViewport>
    </section>
  )
}

/** Everyone else: the public product categories (real reference data) and what each audience gets. */
export function ProductCategoriesBand() {
  const { t } = useTranslation()
  const name = useLocalizedName()
  return (
    <NearViewport minHeight="8rem">
      <AsyncPage load={(signal) => marketplace.listCategories(signal)} skeleton={<span />}>
        {(categories) =>
          categories.length === 0 ? null : (
            <section className={styles.block} aria-labelledby="categories-chips-title">
              <Reveal>
                <SectionHeader title={<span id="categories-chips-title">{t('home.categoriesChipsTitle')}</span>} description={t('home.categoriesChipsBody')} />
              </Reveal>
              <Reveal>
                <ul className={styles.chips} data-testid="product-categories">
                  {categories.slice(0, 12).map((category) => (
                    <li key={category.id}>
                      <span className={`${styles.chip} ${styles.chipStatic}`}>
                        <Icon name="cart" size={14} />
                        {name(category)}
                      </span>
                    </li>
                  ))}
                </ul>
              </Reveal>
            </section>
          )
        }
      </AsyncPage>
    </NearViewport>
  )
}

/**
 * REAL numbers only: counts the API already returns (verified providers, published jobs, listed
 * properties, product categories). A stat whose request fails is simply not shown.
 */
export function PlatformStats() {
  const { t, i18n } = useTranslation()
  return (
    <NearViewport minHeight="5rem">
      <AsyncPage
        load={async (signal) => {
          const settled = await Promise.allSettled([
            providersApi.listProviders({ page_size: 1 }, signal),
            jobsApi.listJobs({ page_size: 1 }, signal),
            realEstate.listListings({}, signal),
            marketplace.listCategories(signal),
          ])
          const ok = <T,>(r: PromiseSettledResult<T>) => (r.status === 'fulfilled' ? r.value : null)
          return { providers: ok(settled[0]), jobs: ok(settled[1]), listings: ok(settled[2]), categories: ok(settled[3]) }
        }}
        skeleton={<span />}
      >
        {(stats) => {
          const items: { icon: IconName; value: number; label: string }[] = []
          if (stats.providers && stats.providers.count > 0) items.push({ icon: 'shieldCheck', value: stats.providers.count, label: t('home.statsProviders') })
          if (stats.jobs && stats.jobs.count > 0) items.push({ icon: 'briefcase', value: stats.jobs.count, label: t('home.statsJobs') })
          if (stats.listings && stats.listings.count > 0) items.push({ icon: 'building', value: stats.listings.count, label: t('home.statsListings') })
          if (stats.categories && stats.categories.length > 0) items.push({ icon: 'cart', value: stats.categories.length, label: t('home.statsCategories') })
          if (items.length === 0) return null
          return (
            <ul className={styles.stats} data-testid="platform-stats">
              {items.map((item) => (
                <StatChip key={item.label} icon={item.icon} value={<CountUp value={item.value} locale={i18n.language} />} label={item.label} />
              ))}
            </ul>
          )
        }}
      </AsyncPage>
    </NearViewport>
  )
}
