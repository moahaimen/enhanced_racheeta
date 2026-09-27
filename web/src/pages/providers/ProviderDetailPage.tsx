import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'

import { ApiError, providers as providersApi, reservations as reservationsApi } from '../../api'
import type { ProviderPublic } from '../../api'
import { useAuth } from '../../auth/useAuth'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Avatar,
  Badge,
  buttonClassName,
  Container,
  EmptyState,
  ErrorState,
  Icon,
  LinkButton,
  LoadingState,
  PageStack,
  PROVIDER_TYPE_ICON,
  SectionCard,
} from '../../design-system'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import styles from './ProviderDetailPage.module.css'

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
          <h1 id="provider-title" className={styles.heroTitle}>{provider.display_name}</h1>
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
                {provider.services.map((service) => (
                  <li key={service.id} className={styles.service}>
                    <div className={styles.serviceText}>
                      <div className={styles.serviceTitle}>{service.title}</div>
                      {service.specialty ? <div className="text-caption">{name(service.specialty)}</div> : null}
                      {service.description ? <p className="text-secondary prewrap">{service.description}</p> : null}
                      {service.duration_minutes ? (
                        <div className="text-caption cluster" style={{ marginBlockStart: 'var(--space-1)' }}>
                          <Icon name="clock" size={14} /> {t('providerDetail.duration', { minutes: service.duration_minutes })}
                        </div>
                      ) : null}
                    </div>
                    <span className={`${styles.servicePrice} ltr`}>
                      {Number(service.price).toLocaleString(i18n.language)} {service.currency}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>

          <BookingSection provider={provider} />
        </PageStack>

        <PageStack>
          {provider.specialties.length > 0 ? (
            <SectionCard title={t('providerDetail.specialties')} headingLevel={2}>
              <ul className={styles.chips}>
                {provider.specialties.map((specialty) => (
                  <li key={specialty.id}><Badge tone="outline">{name(specialty)}</Badge></li>
                ))}
              </ul>
            </SectionCard>
          ) : null}

          {hasContact ? (
            <SectionCard title={t('providerDetail.contact')} headingLevel={2}>
              <dl className={styles.facts}>
                {provider.phone ? <><dt><Icon name="phone" size={14} /> {t('providerDetail.phone')}</dt><dd className="ltr">{provider.phone}</dd></> : null}
                {provider.public_email ? <><dt><Icon name="mail" size={14} /> {t('providerDetail.email')}</dt><dd className="ltr">{provider.public_email}</dd></> : null}
                {provider.website ? <><dt><Icon name="link" size={14} /> {t('providerDetail.website')}</dt><dd className="ltr"><a href={provider.website} rel="noopener noreferrer" target="_blank">{provider.website}</a></dd></> : null}
                {provider.address ? <><dt><Icon name="mapPin" size={14} /> {t('providerDetail.address')}</dt><dd>{provider.address}</dd></> : null}
                {provider.latitude && provider.longitude ? <><dt><Icon name="globe" size={14} /> {t('providerDetail.location')}</dt><dd className="ltr">{provider.latitude}, {provider.longitude}</dd></> : null}
              </dl>
            </SectionCard>
          ) : null}

          {provider.related_providers.length > 0 ? (
            <SectionCard title={provider.kind === 'PRACTITIONER' ? t('providerDetail.worksAt') : t('providerDetail.team')} headingLevel={2}>
              <ul className={styles.related}>
                {provider.related_providers.map((related) => (
                  <li key={related.id} className={styles.relatedItem}>
                    <Avatar src={related.image_url || null} name={related.display_name} size="sm" fallback={<Icon name={PROVIDER_TYPE_ICON[related.provider_type]} size={18} />} />
                    <div>
                      <Link to={`/providers/${related.id}`}>{related.display_name}</Link>
                      <div className="text-caption">{t(`providerTypes.${related.provider_type}`)}</div>
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

function BookingSection({ provider }: { provider: ProviderPublic }) {
  const { t, i18n } = useTranslation()
  const { status, account } = useAuth()
  const slots = useAsyncData((signal) => reservationsApi.listAvailability(provider.id, {}, signal), [provider.id])
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  return (
    <SectionCard title={t('reservations.bookTitle')} description={t('reservations.bookIntro')} headingLevel={2}>
      {success ? <Alert kind="success">{t('reservations.booked')}</Alert> : null}
      {error ? <Alert kind="error">{error}</Alert> : null}
      {slots.loading ? (
        <LoadingState />
      ) : slots.error ? (
        <ErrorState error={slots.error} onRetry={slots.reload} />
      ) : (slots.data ?? []).length === 0 ? (
        <EmptyState icon="calendar" title={t('reservations.noAvailability')} />
      ) : (
        <ul className={styles.services}>
          {(slots.data ?? []).map((slot) => (
            <li key={slot.id} className={styles.service} data-testid="availability-slot">
              <div className={styles.serviceText}>
                <div className={styles.serviceTitle}>{slot.service.title}</div>
                <div className="text-caption cluster">
                  <Icon name="calendar" size={14} /> {new Date(slot.starts_at).toLocaleString(i18n.language)}
                </div>
                <div className="text-caption cluster">
                  <Icon name="clock" size={14} /> {t('providerDetail.duration', { minutes: slot.service.duration_minutes ?? 0 })}
                </div>
              </div>
              {status === 'anonymous' ? (
                <LinkButton to="/login" state={{ from: `/providers/${provider.id}` }} size="sm">
                  {t('reservations.loginToBook')}
                </LinkButton>
              ) : account?.role === 'PATIENT' ? (
                <ApiActionButton
                  size="sm"
                  action={() => reservationsApi.createReservation(slot.id)}
                  onSuccess={() => {
                    setSuccess(true)
                    setError(null)
                    slots.reload()
                  }}
                  onError={(err) => setError(toErrorMessage(err))}
                  pendingLabel={t('reservations.booking')}
                >
                  {t('reservations.book')}
                </ApiActionButton>
              ) : (
                <Badge tone="outline">{t('reservations.patientOnly')}</Badge>
              )}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  )
}
