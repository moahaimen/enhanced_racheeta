import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'

import { providers as providersApi, reference, PROVIDER_TYPES } from '../api'
import type { Governorate, ProviderType } from '../api'
import { useAuth } from '../auth/useAuth'
import {
  AsyncPage,
  Badge,
  Button,
  Container,
  EmptyState,
  FeatureCard,
  Icon,
  LinkButton,
  PROVIDER_TYPE_ICON,
  ProviderCard,
  ProviderCardSkeleton,
  SearchField,
  SectionHeader,
  Select,
  Spinner,
} from '../design-system'
import { useLocalizedName } from '../i18n/localized'
import styles from './HomePage.module.css'

const UPCOMING_MODULES = [
  { key: 'reservations', icon: 'calendar' },
  { key: 'offers', icon: 'tag' },
  { key: 'jobs', icon: 'briefcase' },
  { key: 'marketplace', icon: 'cart' },
  { key: 'realEstate', icon: 'home' },
] as const

export function HomePage() {
  const { t } = useTranslation()
  const { status, account } = useAuth()
  const isProvider = status === 'authenticated' && account?.role === 'PROVIDER'
  // An authenticated non-provider cannot register again (PublicOnly would
  // bounce them to /profile) and there is no self-service role change.
  const isOtherRole = status === 'authenticated' && !isProvider

  return (
    <>
      <section className={styles.hero} aria-labelledby="hero-title">
        <Container width="xl">
          <div className={styles.heroInner}>
            <div>
              <span className={styles.eyebrow}>
                <Icon name="sparkle" size={16} />
                {t('home.heroEyebrow')}
              </span>
              <h1 id="hero-title" className={styles.title}>
                {t('home.heroTitle')}
              </h1>
              <p className={styles.body}>{t('home.heroBody')}</p>
              <div className={styles.ctas}>
                <LinkButton to="/providers" size="lg" trailing={<Icon name="arrowForward" size={18} flipInRtl />}>
                  {t('home.heroPrimary')}
                </LinkButton>
                {status === 'anonymous' ? (
                  <LinkButton to="/register" size="lg" variant="secondary">
                    {t('home.heroSecondary')}
                  </LinkButton>
                ) : isProvider ? (
                  <LinkButton to="/provider/profile" size="lg" variant="secondary">
                    {t('home.heroProvider')}
                  </LinkButton>
                ) : null}
              </div>
              <ul className={styles.trust}>
                <li>
                  <Icon name="shieldCheck" size={18} />
                  {t('home.heroTrust1')}
                </li>
                <li>
                  <Icon name="user" size={18} />
                  {t('home.heroTrust2')}
                </li>
                <li>
                  <Icon name="globe" size={18} />
                  {t('home.heroTrust3')}
                </li>
              </ul>
            </div>
            <HeroArt />
          </div>
        </Container>
      </section>

      <Container width="xl" section="tight">
        <SearchBlock />
      </Container>

      <Container width="xl" section="tight" as="section" aria-labelledby="services-title">
        <SectionHeader title={<span id="services-title">{t('home.servicesTitle')}</span>} description={t('home.servicesBody')} />
        <div className={styles.services}>
          <FeatureCard
            icon={<Icon name={PROVIDER_TYPE_ICON.DOCTOR} size={22} />}
            title={t('modules.providers')}
            action={
              <LinkButton to="/providers" variant="subtle" size="sm" trailing={<Icon name="arrowForward" size={16} flipInRtl />}>
                {t('common.browse')}
              </LinkButton>
            }
          >
            {t('home.services.providers')}
          </FeatureCard>
          {UPCOMING_MODULES.map((m) => (
            <FeatureCard
              key={m.key}
              icon={<Icon name={m.icon} size={22} />}
              title={t(`modules.${m.key}`)}
              upcoming={<Badge tone="outline">{t('common.soon')}</Badge>}
            >
              {t(`home.services.${m.key}`)}
            </FeatureCard>
          ))}
        </div>
      </Container>

      <Container width="xl" section="tight" as="section" aria-labelledby="featured-title">
        <SectionHeader
          title={<span id="featured-title">{t('home.featuredTitle')}</span>}
          description={t('home.featuredBody')}
          actions={
            <LinkButton to="/providers" variant="ghost" size="sm">
              {t('home.featuredAll')}
            </LinkButton>
          }
        />
        <AsyncPage
          load={(signal) => providersApi.listProviders({ ordering: '-created_at', page_size: 6 }, signal)}
          skeleton={
            <div className={styles.providers}>
              {Array.from({ length: 3 }, (_, i) => (
                <ProviderCardSkeleton key={i} />
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
              <div className={styles.providers}>
                {page.results.map((provider) => (
                  <ProviderCard key={provider.id} provider={provider} />
                ))}
              </div>
            )
          }
        </AsyncPage>
      </Container>

      <Container width="xl" section="tight" as="section" aria-labelledby="why-title">
        <SectionHeader title={<span id="why-title">{t('home.whyTitle')}</span>} />
        <div className={styles.why}>
          <FeatureCard icon={<Icon name="shieldCheck" size={22} />} title={t('home.why.verifiedTitle')}>
            {t('home.why.verifiedBody')}
          </FeatureCard>
          <FeatureCard icon={<Icon name="user" size={22} />} title={t('home.why.accountTitle')}>
            {t('home.why.accountBody')}
          </FeatureCard>
          <FeatureCard icon={<Icon name="globe" size={22} />} title={t('home.why.arabicTitle')}>
            {t('home.why.arabicBody')}
          </FeatureCard>
        </div>
      </Container>

      <Container width="xl" section="tight">
        <div className={styles.cta} data-testid="provider-cta">
          <div>
            <h2>{t('home.ctaTitle')}</h2>
            <p>{isOtherRole ? t('home.ctaOtherRole') : t('home.ctaBody')}</p>
          </div>
          {status === 'restoring' ? null : isOtherRole ? (
            <Badge tone="outline" className={styles.ctaNote}>
              {t(`roles.${account?.role ?? 'PATIENT'}`)}
            </Badge>
          ) : (
            <LinkButton to={isProvider ? '/provider/profile' : '/register'} size="lg" className={styles.ctaButton}>
              {isProvider ? t('home.heroProvider') : t('home.ctaButton')}
            </LinkButton>
          )}
        </div>
      </Container>
    </>
  )
}

function HeroArt() {
  const tiles = [
    { icon: 'stethoscope', tone: styles.tileStrong },
    { icon: 'hospital', tone: '' },
    { icon: 'pill', tone: styles.tileSoft },
    { icon: 'flask', tone: '' },
    { icon: 'heartPulse', tone: styles.tileStrong },
    { icon: 'calendar', tone: styles.tileSoft },
    { icon: 'mapPin', tone: styles.tileSoft },
    { icon: 'shieldCheck', tone: '' },
    { icon: 'users', tone: '' },
  ] as const
  return (
    <div className={styles.art} aria-hidden="true">
      {tiles.map((tile) => (
        <span key={tile.icon} className={`${styles.tile} ${tile.tone}`.trim()}>
          <Icon name={tile.icon} size={30} />
        </span>
      ))}
      <span className={styles.artCaption}>
        <span className={styles.pulse} />
      </span>
    </div>
  )
}

function SearchBlock() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const name = useLocalizedName()
  const [type, setType] = useState<ProviderType | ''>('')
  const [governorate, setGovernorate] = useState('')
  const [search, setSearch] = useState('')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const params = new URLSearchParams()
    if (type) params.set('type', type)
    if (governorate) params.set('governorate', governorate)
    if (search.trim()) params.set('search', search.trim())
    navigate(`/providers${params.toString() ? `?${params}` : ''}`)
  }

  return (
    <section className="card-block" aria-labelledby="search-title">
      <SectionHeader headingLevel={2} title={<span id="search-title">{t('home.searchTitle')}</span>} description={t('home.searchBody')} />
      <AsyncPage
        load={(signal) => reference.listGovernorates(undefined, signal)}
        skeleton={
          <div className="cluster">
            <Spinner size="sm" /> <span className="text-muted">{t('providers.loadingFilters')}</span>
          </div>
        }
      >
        {(governorates: Governorate[]) => (
          <form className={styles.searchForm} onSubmit={submit} aria-label={t('home.searchTitle')}>
            <Select label={t('providers.type')} value={type} onChange={(e) => setType(e.target.value as ProviderType | '')}>
              <option value="">{t('common.all')}</option>
              {PROVIDER_TYPES.map((code) => (
                <option key={code} value={code}>
                  {t(`providerTypes.${code}`)}
                </option>
              ))}
            </Select>
            <Select label={t('providers.governorate')} value={governorate} onChange={(e) => setGovernorate(e.target.value)}>
              <option value="">{t('common.all')}</option>
              {governorates.map((g) => (
                <option key={g.id} value={g.id}>
                  {name(g)}
                </option>
              ))}
            </Select>
            <SearchField label={t('common.search')} placeholder={t('providers.searchPlaceholder')} value={search} onChange={(e) => setSearch(e.target.value)} />
            <Button type="submit" size="lg" leading={<Icon name="search" size={18} />}>
              {t('home.searchSubmit')}
            </Button>
          </form>
        )}
      </AsyncPage>
    </section>
  )
}
