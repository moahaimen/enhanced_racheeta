import { useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { jobs as jobsApi, marketplace, providers as providersApi, realEstate, reference } from '../../api'
import type { ProviderCard as ProviderCardData, Specialty } from '../../api'
import {
  AsyncPage,
  Avatar,
  Badge,
  CountUp,
  EmptyState,
  Icon,
  JobCard,
  JobCardSkeleton,
  LinkButton,
  NearViewport,
  PersonPlaceholder,
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

/** Compact doctor card of the approved homepage: portrait, name, specialty, rating, city, profile pill. */
function DoctorCard({ provider }: { provider: ProviderCardData }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const text = useScriptText()
  const specialty = provider.specialties[0]
  const rated = provider.review_count > 0 && provider.average_rating !== null
  return (
    <article className={styles.doctor}>
      <div className={styles.doctorTop}>
        <div className={styles.doctorText}>
          <h3 className={styles.doctorName}>
            <Link to={`/providers/${provider.id}`} className={styles.stretch}>
              {text(provider.display_name)}
            </Link>
          </h3>
          <p className={styles.doctorRole}>{specialty ? name(specialty) : t(`providerTypes.${provider.provider_type}`)}</p>
          {rated ? (
            <p className={styles.doctorRating}>
              <span className={styles.star} aria-hidden="true">★</span>
              <span>{provider.average_rating!.toFixed(1)}</span>
              <span className={styles.reviewCount}>({t('reviews.count', { count: provider.review_count })})</span>
            </p>
          ) : (
            <p className={styles.doctorVerified}>
              <Icon name="shieldCheck" size={14} /> {t('verification.VERIFIED')}
            </p>
          )}
          <p className={styles.doctorPlace}>
            <Icon name="mapPin" size={14} />
            {name(provider.governorate)}
          </p>
        </div>
        <Avatar
          src={provider.image_url || null}
          name={provider.display_name}
          size="lg"
          className={styles.doctorAvatar}
          fallback={<PersonPlaceholder seed={provider.id} size={72} />}
        />
      </div>
      <span className={styles.doctorCta} aria-hidden="true">
        {t('providers.viewProfile')}
      </span>
    </article>
  )
}

/** Featured doctors as a horizontal row with previous/next controls (scroll-snap, keyboard reachable). */
export function FeaturedDoctorsRow() {
  const { t } = useTranslation()
  const rail = useRef<HTMLDivElement>(null)
  const scroll = (direction: 1 | -1) => {
    const el = rail.current
    if (!el) return
    const rtl = getComputedStyle(el).direction === 'rtl'
    const step = el.clientWidth * 0.8 * direction * (rtl ? -1 : 1)
    el.scrollBy({ left: step, behavior: 'smooth' })
  }
  return (
    <section className={styles.block} aria-labelledby="doctors-title">
      <div className={styles.rowHead}>
        <h2 id="doctors-title" className={styles.rowTitle}>
          {t('home.doctorsTitle')}
        </h2>
        <Link to="/providers?kind=PRACTITIONER" className={styles.rowLink}>
          {t('home.viewAll')}
          <Icon name="arrowForward" size={16} flipInRtl />
        </Link>
      </div>
      <NearViewport minHeight="12rem">
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
              <div className={styles.railWrap}>
                <button type="button" className={`${styles.railButton} ${styles.railPrev}`} onClick={() => scroll(-1)} aria-label={t('home.carouselPrev')}>
                  <Icon name="chevronForward" size={20} flipInRtl />
                </button>
                <div className={styles.rail} ref={rail} data-testid="featured-doctors">
                  {[...page.results]
                    .sort(byRating)
                    .slice(0, 8)
                    .map((provider) => (
                      <DoctorCard key={provider.id} provider={provider} />
                    ))}
                </div>
                <button type="button" className={`${styles.railButton} ${styles.railNext}`} onClick={() => scroll(1)} aria-label={t('home.carouselNext')}>
                  <Icon name="chevronBack" size={20} flipInRtl />
                </button>
              </div>
            )
          }
        </AsyncPage>
      </NearViewport>
    </section>
  )
}

/** Specialty slugs shown as "popular services" (in this order, when the API has them) and their icons. */
const POPULAR: [string, IconName][] = [
  ['general-medicine', 'stethoscope'],
  ['laboratory-medicine', 'flask'],
  ['dentistry', 'tooth'],
  ['pediatrics', 'baby'],
  ['cardiology', 'heart'],
  ['orthopedics', 'bone'],
  ['ophthalmology', 'eye'],
]

/** Popular medical services: real specialties from the API, each opening the filtered directory. */
export function PopularServices() {
  const { t } = useTranslation()
  const name = useLocalizedName()
  return (
    <NearViewport minHeight="6rem">
      <AsyncPage load={(signal) => reference.listSpecialties(signal)} skeleton={<span />}>
        {(specialties: Specialty[]) => {
          const bySlug = new Map(specialties.map((s) => [s.slug, s]))
          const items = POPULAR.flatMap(([slug, icon]) => {
            const specialty = bySlug.get(slug)
            return specialty ? [{ specialty, icon }] : []
          })
          if (items.length === 0) return null
          return (
            <section className={styles.block} aria-labelledby="popular-title">
              <div className={styles.rowHead}>
                <h2 id="popular-title" className={styles.rowTitle}>
                  {t('home.popularTitle')}
                </h2>
                <Link to="/providers" className={styles.rowLink}>
                  {t('home.viewAll')}
                  <Icon name="arrowForward" size={16} flipInRtl />
                </Link>
              </div>
              <ul className={styles.popular} data-testid="popular-services">
                {items.map(({ specialty, icon }) => (
                  <li key={specialty.id}>
                    <Link to={`/providers?specialty=${encodeURIComponent(specialty.slug)}`} className={styles.popularItem}>
                      <Icon name={icon} size={30} />
                      <span>{name(specialty)}</span>
                    </Link>
                  </li>
                ))}
                <li>
                  <Link to="/providers" className={styles.popularItem}>
                    <Icon name="dots" size={30} />
                    <span>{t('home.popularMore')}</span>
                  </Link>
                </li>
              </ul>
            </section>
          )
        }}
      </AsyncPage>
    </NearViewport>
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
            <section className={styles.block} aria-labelledby="categories-chips-title" id="product-categories">
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
