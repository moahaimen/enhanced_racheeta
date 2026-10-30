import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useAuth } from '../auth/useAuth'
import { Badge, Container, Icon, LinkButton, Reveal, type IconName } from '../design-system'
import { HeroVisual } from './home/HeroVisual'
import { useTalentTarget } from './home/talentTarget'
import { HeroSearch } from './home/HeroSearch'
import {
  Facilities,
  FeaturedDoctorsRow,
  LatestJobs,
  LatestProperties,
  PlatformStats,
  PopularServices,
  ProductCategoriesBand,
  ProductsForProviders,
} from './home/HomeSections'
import styles from './home/Home.module.css'

type Target = { to: string; state?: { from: string } }

type Feature = { key: string; icon: IconName; to: string; tone: 'teal' | 'white'; title: string; body: string; cta: string }

/** One of the six principal destinations: a teal or a white card, icon chip, title, text, pill. */
function FeatureCard({ feature }: { feature: Feature }) {
  return (
    <article className={styles.feature} data-tone={feature.tone}>
      <span className={styles.featureIcon} aria-hidden="true">
        <Icon name={feature.icon} size={28} />
      </span>
      <h3 className={styles.featureTitle}>{feature.title}</h3>
      <p className={styles.featureBody}>{feature.body}</p>
      {feature.to.startsWith('#') ? (
        <a href={feature.to} className={styles.featurePill} aria-label={`${feature.cta} — ${feature.title}`}>
          {feature.cta}
          <Icon name="arrowForward" size={16} flipInRtl />
        </a>
      ) : (
        <Link to={feature.to} className={styles.featurePill} aria-label={`${feature.cta} — ${feature.title}`}>
          {feature.cta}
          <Icon name="arrowForward" size={16} flipInRtl />
        </Link>
      )}
    </article>
  )
}

export function HomePage() {
  const { t } = useTranslation()
  const { status, account } = useAuth()
  const isProvider = status === 'authenticated' && account?.role === 'PROVIDER'
  const isCompany = status === 'authenticated' && account?.role === 'MEDICAL_COMPANY'
  const isAnonymous = status === 'anonymous'
  // An authenticated non-provider cannot register again (PublicOnly would
  // bounce them to /profile) and there is no self-service role change.
  const isOtherRole = status === 'authenticated' && !isProvider

  // The medical marketplace is B2B: providers browse it, companies manage it. Anonymous visitors
  // are sent through login by the route guard. Patients and sellers are not offered a dead end:
  // their products/companies cards open the public product categories further down this page.
  const supplierTarget: Target | null = isCompany ? { to: '/company' } : isProvider || isAnonymous ? { to: '/marketplace' } : null
  const catalogueTo = supplierTarget?.to ?? '#product-categories'
  const estateTarget: Target = status === 'authenticated' && account?.role === 'REAL_ESTATE_SELLER' ? { to: '/real-estate/owner' } : { to: '/real-estate' }
  const talentTarget = useTalentTarget()

  // Approved layout: 3 × 2, alternating teal and white (reading order follows the page direction).
  const features: Feature[] = [
    { key: 'doctors', icon: 'doctor', to: '/providers?kind=PRACTITIONER', tone: 'teal', title: t('home.feat.doctorsTitle'), body: t('home.feat.doctorsBody'), cta: t('home.feat.doctorsCta') },
    { key: 'facilities', icon: 'hospital', to: '/providers?kind=FACILITY', tone: 'white', title: t('home.feat.facilitiesTitle'), body: t('home.feat.facilitiesBody'), cta: t('home.feat.facilitiesCta') },
    { key: 'jobs', icon: 'briefcase', to: '/jobs', tone: 'teal', title: t('home.feat.jobsTitle'), body: t('home.feat.jobsBody'), cta: t('home.feat.jobsCta') },
    { key: 'estate', icon: 'building', to: estateTarget.to, tone: 'white', title: t('home.feat.estateTitle'), body: t('home.feat.estateBody'), cta: t('home.feat.estateCta') },
    { key: 'products', icon: 'box', to: catalogueTo, tone: 'teal', title: t('home.feat.productsTitle'), body: t('home.feat.productsBody'), cta: t('home.feat.productsCta') },
    { key: 'companies', icon: 'pill', to: catalogueTo, tone: 'white', title: t('home.feat.companiesTitle'), body: t('home.feat.companiesBody'), cta: isCompany ? t('home.feat.companiesWorkspaceCta') : t('home.feat.companiesCta') },
  ]

  return (
    <>
      <section className={styles.hero} aria-labelledby="hero-title">
        <Container width="xl">
          <div className={styles.heroInner}>
            <div className={styles.heroText}>
              <h1 id="hero-title" className={styles.title}>
                <span>{t('home.heroTitleLead')}</span> <span className={styles.titleAccent}>{t('home.heroTitleAccent')}</span>
              </h1>
              <p className={styles.tagline}>{t('home.heroTagline')}</p>
              <p className={styles.body}>{t('home.heroBody')}</p>
              <section className={styles.searchCard} aria-labelledby="search-title">
                <h2 id="search-title" className="visually-hidden">
                  {t('home.searchTitle')}
                </h2>
                <HeroSearch />
              </section>
              {isAnonymous || isProvider ? (
                <div className={styles.ctas}>
                  {isAnonymous ? (
                    <LinkButton to="/register" trailing={<Icon name="arrowForward" size={16} flipInRtl />}>
                      {t('home.heroStart')}
                    </LinkButton>
                  ) : (
                    <LinkButton to="/provider/profile" trailing={<Icon name="arrowForward" size={16} flipInRtl />}>
                      {t('home.heroProvider')}
                    </LinkButton>
                  )}
                </div>
              ) : null}
            </div>
            <HeroVisual chip={t('home.heroChip')} />
          </div>
        </Container>
      </section>

      <Container width="xl" className={styles.featuresWrap}>
        <nav className={styles.features} aria-label={t('home.categoriesTitle')}>
          {features.map((feature, index) => (
            <Reveal key={feature.key} index={index}>
              <FeatureCard feature={feature} />
            </Reveal>
          ))}
        </nav>
      </Container>

      <Container width="xl" className={styles.blockWrap}>
        <FeaturedDoctorsRow />
        <PopularServices />
      </Container>

      <Container width="xl" className={styles.statsWrap}>
        <PlatformStats />
      </Container>


      <div className={styles.tinted}>
        <Container width="xl" className={styles.blockWrap}>
          <Facilities />
        </Container>
      </div>

      <Container width="xl" className={styles.blockWrap}>
        <LatestJobs />
        <div className={styles.jobsBand} data-testid="home-jobs">
          <div className={styles.jobsBandText}>
            <span className={styles.eyebrowOnDark}>
              <Icon name="briefcase" size={16} />
              {t('modules.jobs')}
            </span>
            <h2 id="jobs-title">{t('home.jobsTitle')}</h2>
            <p>{t('home.jobsBody')}</p>
          </div>
          <div className={styles.jobsActions}>
            <div>
              <LinkButton to="/jobs" size="lg" className={styles.onDark} trailing={<Icon name="arrowForward" size={18} flipInRtl />}>
                {t('home.jobsSeek')}
              </LinkButton>
              <p>{t('home.jobsSeekHint')}</p>
            </div>
            <div>
              <LinkButton to={talentTarget.to} state={talentTarget.state} size="lg" variant="secondary" trailing={<Icon name="users" size={18} />}>
                {t('home.jobsHire')}
              </LinkButton>
              <p>{t('home.jobsHireHint')}</p>
            </div>
          </div>
        </div>
      </Container>

      <div className={styles.tinted}>
        <Container width="xl" className={styles.blockWrap}>
          <LatestProperties />
        </Container>
      </div>

      <Container width="xl" className={styles.blockWrap}>
        {isProvider ? <ProductsForProviders /> : <ProductCategoriesBand />}
      </Container>

      <Container width="xl" className={styles.blockWrap}>
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
