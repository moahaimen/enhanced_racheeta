import { useTranslation } from 'react-i18next'

import { useAuth } from '../auth/useAuth'
import {
  Badge,
  CategoryTile,
  Container,
  Icon,
  LinkButton,
  Reveal,
  ServiceTile,
  type Accent,
  type IconName,
} from '../design-system'
import { HeroArt, SceneCompanies, SceneDoctors, SceneEstate, SceneHospitals, SceneJobs, SceneProducts } from './home/art'
import { HeroSearch } from './home/HeroSearch'
import {
  Facilities,
  FeaturedDoctors,
  LatestJobs,
  LatestProperties,
  PlatformStats,
  ProductCategoriesBand,
  ProductsForProviders,
  SpecialtyChips,
} from './home/HomeSections'
import styles from './home/Home.module.css'

type Target = { to: string; state?: { from: string } }

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
  // are sent through login by the route guard; patients and sellers are not offered a dead end.
  const supplierTarget: Target | null = isCompany ? { to: '/company' } : isProvider || isAnonymous ? { to: '/marketplace' } : null
  const estateTarget: Target = status === 'authenticated' && account?.role === 'REAL_ESTATE_SELLER' ? { to: '/real-estate/owner' } : { to: '/real-estate' }
  const talentTarget: Target = status === 'authenticated' ? { to: '/employer/talent' } : { to: '/login', state: { from: '/employer' } }

  const tiles: { to: string; icon: IconName; label: string; accent: Accent }[] = [
    { to: '/providers?kind=PRACTITIONER', icon: 'stethoscope', label: t('home.catDoctors'), accent: 'teal' },
    { to: '/providers?kind=FACILITY', icon: 'hospital', label: t('home.catFacilities'), accent: 'blue' },
    { to: '/jobs', icon: 'briefcase', label: t('home.catJobs'), accent: 'indigo' },
    { to: estateTarget.to, icon: 'building', label: t('home.catEstate'), accent: 'coral' },
  ]
  if (supplierTarget) tiles.push({ to: supplierTarget.to, icon: 'cart', label: t('home.catSuppliers'), accent: 'mint' })

  return (
    <>
      <section className={styles.hero} aria-labelledby="hero-title">
        <span className={`${styles.orb} ${styles.orbA}`} aria-hidden="true" />
        <span className={`${styles.orb} ${styles.orbB}`} aria-hidden="true" />
        <Container width="xl">
          <div className={styles.heroInner}>
            <div className={styles.heroText}>
              <span className={styles.eyebrow}>
                <Icon name="sparkle" size={16} />
                {t('home.heroEyebrow')}
              </span>
              <h1 id="hero-title" className={styles.title}>
                <span>{t('home.heroTitleLead')}</span> <span className={styles.titleAccent}>{t('home.heroTitleAccent')}</span>
              </h1>
              <p className={styles.tagline}>{t('home.heroTagline')}</p>
              <p className={styles.body}>{t('home.heroBody')}</p>
              {isAnonymous || isProvider ? (
                <div className={styles.ctas}>
                  {isAnonymous ? (
                    <LinkButton to="/register" size="lg" trailing={<Icon name="arrowForward" size={18} flipInRtl />}>
                      {t('home.heroSecondary')}
                    </LinkButton>
                  ) : (
                    <LinkButton to="/provider/profile" size="lg" trailing={<Icon name="arrowForward" size={18} flipInRtl />}>
                      {t('home.heroProvider')}
                    </LinkButton>
                  )}
                </div>
              ) : null}
              <ul className={styles.trust}>
                <li>
                  <Icon name="checkCircle" size={18} />
                  {t('home.heroTrust1')}
                </li>
                <li>
                  <Icon name="checkCircle" size={18} />
                  {t('home.heroTrust2')}
                </li>
                <li>
                  <Icon name="checkCircle" size={18} />
                  {t('home.heroTrust3')}
                </li>
              </ul>
            </div>
            <div className={styles.heroVisual} aria-hidden="true">
              <HeroArt className={styles.heroArt} />
              <span className={styles.heroChip}>
                <Icon name="heartPulse" size={22} />
                {t('home.heroChip')}
              </span>
            </div>
          </div>
        </Container>
      </section>

      <Container width="xl" className={styles.searchWrap}>
        <section className={styles.searchCard} aria-labelledby="search-title">
          <h2 id="search-title" className="visually-hidden">
            {t('home.searchTitle')}
          </h2>
          <HeroSearch />
          <nav className={styles.tiles} aria-label={t('home.categoriesTitle')}>
            {tiles.map((tile) => (
              <CategoryTile key={tile.label} {...tile} />
            ))}
          </nav>
        </section>
      </Container>

      <Container width="xl" className={styles.statsWrap}>
        <PlatformStats />
      </Container>

      <Container width="xl" as="section" className={styles.blockWrap} aria-labelledby="services-title">
        <Reveal className={styles.sectionHead}>
          <h2 id="services-title">{t('home.servicesTitle')}</h2>
          <p>{t('home.servicesBody')}</p>
        </Reveal>
        <div className={styles.services}>
          <Reveal index={0}>
            <ServiceTile to="/providers?kind=PRACTITIONER" art={<SceneDoctors />} title={t('home.svc.doctorsTitle')} description={t('home.svc.doctorsBody')} accent="teal" />
          </Reveal>
          <Reveal index={1}>
            <ServiceTile to="/providers?kind=FACILITY" art={<SceneHospitals />} title={t('home.svc.facilitiesTitle')} description={t('home.svc.facilitiesBody')} accent="blue" />
          </Reveal>
          <Reveal index={2}>
            {supplierTarget ? (
              <ServiceTile
                to={supplierTarget.to}
                art={<SceneProducts />}
                title={isCompany ? t('home.svc.companyTitle') : t('home.svc.productsTitle')}
                description={isCompany ? t('home.svc.companyBody') : t('home.svc.productsBody')}
                accent="aqua"
              />
            ) : (
              <ServiceTile to="/dashboard" art={<SceneProducts />} title={t('home.svc.dashboardTitle')} description={t('home.svc.dashboardBody')} accent="aqua" />
            )}
          </Reveal>
          <Reveal index={3}>
            <ServiceTile to="/jobs" art={<SceneJobs />} title={t('home.svc.jobsTitle')} description={t('home.svc.jobsBody')} accent="indigo" />
          </Reveal>
          <Reveal index={4}>
            <ServiceTile
              to={estateTarget.to}
              art={<SceneEstate />}
              title={estateTarget.to === '/real-estate' ? t('home.svc.estateTitle') : t('nav.realEstateWorkspace')}
              description={t('home.svc.estateBody')}
              accent="coral"
            />
          </Reveal>
          <Reveal index={5}>
            <ServiceTile to={talentTarget.to} art={<SceneCompanies />} title={t('home.svc.hireTitle')} description={t('home.svc.hireBody')} accent="mint" />
          </Reveal>
        </div>
      </Container>

      <Container width="xl" className={styles.blockWrap}>
        <FeaturedDoctors />
      </Container>

      <div className={styles.tinted}>
        <Container width="xl" className={styles.blockWrap}>
          <Facilities />
          <SpecialtyChips />
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

      <Container width="xl" className={styles.blockWrap} as="section" aria-labelledby="eco-title">
        <Reveal className={styles.sectionHead}>
          <h2 id="eco-title">{t('home.ecoTitle')}</h2>
          <p>{t('home.ecoBody')}</p>
        </Reveal>
        <div className={styles.eco}>
          {(
            [
              { icon: 'pill', accent: 'teal', title: t('home.eco.pharmaTitle'), body: t('home.eco.pharmaBody'), to: supplierTarget?.to ?? '/register' },
              { icon: 'flask', accent: 'mint', title: t('home.eco.equipTitle'), body: t('home.eco.equipBody'), to: supplierTarget?.to ?? '/register' },
              { icon: 'users', accent: 'indigo', title: t('home.eco.employersTitle'), body: t('home.eco.employersBody'), to: '/jobs' },
              { icon: 'hospital', accent: 'blue', title: t('home.eco.facilitiesTitle'), body: t('home.eco.facilitiesBody'), to: '/providers?kind=FACILITY' },
            ] as { icon: IconName; accent: Accent; title: string; body: string; to: string }[]
          ).map((item, index) => (
            <Reveal key={item.title} index={index}>
              <CategoryTile to={item.to} icon={item.icon} label={item.title} accent={item.accent} />
              <p className={styles.ecoBody}>{item.body}</p>
            </Reveal>
          ))}
        </div>
        {isProvider ? <ProductsForProviders /> : <ProductCategoriesBand />}
      </Container>

      <section className={styles.why} aria-labelledby="why-title">
        <Container width="xl">
          <Reveal className={`${styles.sectionHead} ${styles.onDark}`}>
            <h2 id="why-title">{t('home.whyTitle')}</h2>
          </Reveal>
          <div className={styles.whyGrid}>
            {(
              [
                { icon: 'shieldCheck', title: t('home.why.verifiedTitle'), body: t('home.why.verifiedBody') },
                { icon: 'user', title: t('home.why.accountTitle'), body: t('home.why.accountBody') },
                { icon: 'globe', title: t('home.why.arabicTitle'), body: t('home.why.arabicBody') },
              ] as { icon: IconName; title: string; body: string }[]
            ).map((item, index) => (
              <Reveal key={item.title} index={index} className={styles.whyCard}>
                <span className={styles.whyIcon} aria-hidden="true">
                  <Icon name={item.icon} size={22} />
                </span>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </Reveal>
            ))}
          </div>
        </Container>
      </section>

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
