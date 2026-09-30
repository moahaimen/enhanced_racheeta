import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'

import { ApiError, realEstate as realEstateApi } from '../../api'
import { AsyncPage, Badge, Container, Icon, PageHeader, PageStack, SectionCard } from '../../design-system'
import { useLocalizedName } from '../../i18n/localized'
import { formatArea, formatListingPrice } from './realEstateFormat'
import styles from './RealEstate.module.css'

/** /real-estate/:id — the backend applies the same visibility as the list (a plain 404 otherwise). */
export function RealEstateDetailPage() {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const { id = '' } = useParams()
  const load = async (signal: AbortSignal) => {
    try {
      return await realEstateApi.getListing(id, signal)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) throw new ApiError(404, 'not_found', t('realEstate.notFound'))
      throw e
    }
  }
  const date = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(i18n.language) : '')
  return (
    <Container width="lg">
      <AsyncPage load={load} deps={[id]}>
        {(listing) => (
          <>
            <PageHeader
              eyebrow={
                <Link to="/real-estate" className="cluster">
                  <Icon name="chevronBack" size={14} flipInRtl /> {t('realEstate.title')}
                </Link>
              }
              title={listing.title}
              description={[name(listing.governorate), listing.city ? name(listing.city) : '', listing.district].filter(Boolean).join(' · ')}
              actions={
                <div className="cluster">
                  <Badge tone={listing.transaction_type === 'SALE' ? 'brand' : 'success'}>{t(`transactionTypes.${listing.transaction_type}`)}</Badge>
                  <Badge tone="outline">{t(`propertyTypes.${listing.property_type}`)}</Badge>
                </div>
              }
            />
            <PageStack>
              <SectionCard title={t('realEstate.details')} headingLevel={2}>
                <dl className={styles.facts}>
                  <div>
                    <dt>{t('realEstate.price')}</dt>
                    <dd dir="auto" data-testid="listing-price">
                      {formatListingPrice(listing, i18n.language, t('realEstate.priceOnRequest'))}
                    </dd>
                  </div>
                  {listing.area_sqm !== null ? (
                    <div>
                      <dt>{t('realEstate.area')}</dt>
                      <dd dir="auto">
                        {formatArea(listing.area_sqm, i18n.language)} {t('realEstate.sqm')}
                      </dd>
                    </div>
                  ) : null}
                  {listing.expires_at ? (
                    <div>
                      <dt>{t('realEstate.expiresOn')}</dt>
                      <dd>{date(listing.expires_at)}</dd>
                    </div>
                  ) : null}
                  {listing.latitude !== null && listing.longitude !== null ? (
                    <div>
                      <dt>{t('realEstate.coordinates')}</dt>
                      <dd dir="ltr" data-testid="listing-coordinates">
                        {listing.latitude}, {listing.longitude}
                      </dd>
                    </div>
                  ) : null}
                </dl>
                {listing.description ? <p className="prewrap">{listing.description}</p> : null}
                {listing.facilities ? (
                  <>
                    <h3>{t('realEstate.facilities')}</h3>
                    <p className="prewrap">{listing.facilities}</p>
                  </>
                ) : null}
              </SectionCard>
              <SectionCard title={t('realEstate.suitableUse')} headingLevel={2}>
                <div className="cluster" data-testid="listing-uses">
                  {listing.suitable_uses.map((use) => (
                    <Badge key={use} tone="neutral">
                      {t(`suitableUses.${use}`)}
                    </Badge>
                  ))}
                </div>
              </SectionCard>
              <SectionCard title={t('realEstate.contact')} headingLevel={2}>
                <p>
                  <strong>{listing.seller.display_name}</strong>
                  <span className="text-caption"> · {t(`sellerTypes.${listing.seller.seller_type}`)}</span>
                </p>
                {listing.contact_phone ? (
                  <p dir="ltr" data-testid="listing-phone">
                    <Icon name="phone" size={16} /> {listing.contact_phone}
                  </p>
                ) : null}
                {listing.contact_email ? (
                  <p dir="ltr" data-testid="listing-email">
                    <Icon name="mail" size={16} /> {listing.contact_email}
                  </p>
                ) : null}
              </SectionCard>
            </PageStack>
          </>
        )}
      </AsyncPage>
    </Container>
  )
}
