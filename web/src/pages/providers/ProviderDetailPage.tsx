import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'

import { ApiError, providers as providersApi } from '../../api'
import type { ProviderPublic } from '../../api'
import { AsyncPage, Avatar, Badge, buttonClassName, Container, Icon, LinkButton, PageStack, PROVIDER_TYPE_ICON, SectionCard } from '../../design-system'
import { useLocalizedName } from '../../i18n/localized'
import styles from './ProviderDetailPage.module.css'

/** Public provider profile. Everything shown comes from GET /providers/{id}. */
export function ProviderDetailPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()

  const load = async (signal: AbortSignal) => {
    try {
      return await providersApi.getProvider(id, signal)
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        throw new ApiError(404, 'not_found', t('providerDetail.notFound'))
      }
      throw error
    }
  }

  return (
    <Container width="xl">
      <AsyncPage load={load} deps={[id]}>
        {(provider) => <ProviderDetail provider={provider} />}
      </AsyncPage>
    </Container>
  )
}

function ProviderDetail({ provider }: { provider: ProviderPublic }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const hasContact = provider.phone || provider.public_email || provider.website || provider.address || provider.latitude
  return (
    <PageStack>
      <section className={styles.hero} aria-labelledby="provider-title">
        <Avatar src={provider.image_url || null} name={provider.display_name} size="xl" fallback={<Icon name={PROVIDER_TYPE_ICON[provider.provider_type]} size={40} />} />
        <div className={styles.heroText}>
          <h1 id="provider-title" className={styles.heroTitle}>
            {provider.display_name}
          </h1>
          <div className={styles.heroMeta}>
            <Badge tone="brand">{t(`providerTypes.${provider.provider_type}`)}</Badge>
            <Badge tone="success" leading={<Icon name="shieldCheck" size={12} />}>
              {provider.verified_at
                ? `${t('providerDetail.verifiedSince')} ${new Date(provider.verified_at).toLocaleDateString(i18n.language)}`
                : t('verification.VERIFIED')}
            </Badge>
          </div>
          <p className={styles.heroLocation}>
            <Icon name="mapPin" size={16} />
            {name(provider.governorate)}
            {provider.city ? ` — ${name(provider.city)}` : ''}
          </p>
          <div className={styles.heroActions}>
            {provider.phone ? (
              <a className={`${buttonClassName({ variant: 'secondary' })} ltr`} href={`tel:${provider.phone}`}>
                <Icon name="phone" size={18} /> {provider.phone}
              </a>
            ) : null}
            <LinkButton to="/providers" variant="ghost" leading={<Icon name="chevronBack" size={18} flipInRtl />}>
              {t('providerDetail.backToList')}
            </LinkButton>
          </div>
        </div>
      </section>

      <div className={styles.layout}>
        <PageStack>
          {provider.about ? (
            <SectionCard title={t('providerDetail.about')} headingLevel={2}>
              <p className="prewrap">{provider.about}</p>
            </SectionCard>
          ) : null}

          <SectionCard title={t('providerDetail.services')} headingLevel={2}>
            {provider.services.length === 0 ? (
              <p className="text-muted">{t('providerDetail.noServices')}</p>
            ) : (
              <ul className={styles.services}>
                {provider.services.map((s) => (
                  <li key={s.id} className={styles.service}>
                    <div className={styles.serviceText}>
                      <div className={styles.serviceTitle}>{s.title}</div>
                      {s.specialty ? <div className="text-caption">{name(s.specialty)}</div> : null}
                      {s.description ? <p className="text-secondary prewrap">{s.description}</p> : null}
                      {s.duration_minutes ? (
                        <div className="text-caption cluster" style={{ marginBlockStart: 'var(--space-1)' }}>
                          <Icon name="clock" size={14} /> {t('providerDetail.duration', { minutes: s.duration_minutes })}
                        </div>
                      ) : null}
                    </div>
                    <span className={`${styles.servicePrice} ltr`}>
                      {Number(s.price).toLocaleString(i18n.language)} {s.currency}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <p className={styles.slot} style={{ marginBlockStart: 'var(--space-4)' }}>
              <Icon name="calendar" size={14} /> {t('providerDetail.bookingSoon')}
            </p>
          </SectionCard>
        </PageStack>

        <PageStack>
          {provider.specialties.length > 0 ? (
            <SectionCard title={t('providerDetail.specialties')} headingLevel={2}>
              <ul className={styles.chips}>
                {provider.specialties.map((s) => (
                  <li key={s.id}>
                    <Badge tone="outline">{name(s)}</Badge>
                  </li>
                ))}
              </ul>
            </SectionCard>
          ) : null}

          {hasContact ? (
            <SectionCard title={t('providerDetail.contact')} headingLevel={2}>
              <dl className={styles.facts}>
                {provider.phone ? (
                  <>
                    <dt>
                      <Icon name="phone" size={14} /> {t('providerDetail.phone')}
                    </dt>
                    <dd className="ltr">{provider.phone}</dd>
                  </>
                ) : null}
                {provider.public_email ? (
                  <>
                    <dt>
                      <Icon name="mail" size={14} /> {t('providerDetail.email')}
                    </dt>
                    <dd className="ltr">{provider.public_email}</dd>
                  </>
                ) : null}
                {provider.website ? (
                  <>
                    <dt>
                      <Icon name="link" size={14} /> {t('providerDetail.website')}
                    </dt>
                    <dd className="ltr">
                      <a href={provider.website} rel="noopener noreferrer" target="_blank">
                        {provider.website}
                      </a>
                    </dd>
                  </>
                ) : null}
                {provider.address ? (
                  <>
                    <dt>
                      <Icon name="mapPin" size={14} /> {t('providerDetail.address')}
                    </dt>
                    <dd>{provider.address}</dd>
                  </>
                ) : null}
                {provider.latitude && provider.longitude ? (
                  <>
                    <dt>
                      <Icon name="globe" size={14} /> {t('providerDetail.location')}
                    </dt>
                    <dd className="ltr">
                      {provider.latitude}, {provider.longitude}
                    </dd>
                  </>
                ) : null}
              </dl>
            </SectionCard>
          ) : null}

          {provider.related_providers.length > 0 ? (
            <SectionCard title={provider.kind === 'PRACTITIONER' ? t('providerDetail.worksAt') : t('providerDetail.team')} headingLevel={2}>
              <ul className={styles.related}>
                {provider.related_providers.map((r) => (
                  <li key={r.id} className={styles.relatedItem}>
                    <Avatar src={r.image_url || null} name={r.display_name} size="sm" fallback={<Icon name={PROVIDER_TYPE_ICON[r.provider_type]} size={18} />} />
                    <div>
                      <Link to={`/providers/${r.id}`}>{r.display_name}</Link>
                      <div className="text-caption">{t(`providerTypes.${r.provider_type}`)}</div>
                    </div>
                  </li>
                ))}
              </ul>
            </SectionCard>
          ) : null}
        </PageStack>
      </div>
    </PageStack>
  )
}
