import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'
import type { TFunction } from 'i18next'

import {
  ApiError,
  CONTACT_METHODS,
  PROPERTY_TYPES,
  SELLER_TYPES,
  SUITABLE_USES,
  TRANSACTION_TYPES,
  realEstate as realEstateApi,
  reference,
} from '../../api'
import type { City, ContactMethod, Governorate, ListingWrite, OwnerListing, PropertyType, RealEstateSeller, SellerType, SuitableUse, TransactionType } from '../../api'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Badge,
  Button,
  Checkbox,
  CheckboxGroup,
  Container,
  EmptyState,
  ErrorState,
  FormActions,
  Icon,
  LoadingState,
  PageHeader,
  PageStack,
  Pagination,
  SectionCard,
  Select,
  Spinner,
  StatCard,
  Textarea,
  TextField,
  useFormErrors,
} from '../../design-system'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { ClientValidationError } from '../validation'
import { formatArea, formatListingPrice, fromLocalInput, publicationGaps, toLocalInput } from './realEstateFormat'

const PAGE_SIZE = 20

type Loaded = [RealEstateSeller | null, Governorate[]]

/**
 * A publication/validation refusal from the backend, in the user's language: the
 * typed per-field codes (`apiErrors.<code>`), all of them, not just the first.
 */
function refusalMessage(error: unknown, t: TFunction): string {
  if (error instanceof ApiError && error.code === 'validation_error' && error.codes) {
    const seen = new Set<string>()
    for (const codes of Object.values(error.codes)) {
      for (const code of codes) {
        const text = t(`apiErrors.${code}`, { defaultValue: '' })
        if (text) seen.add(text)
      }
    }
    if (seen.size > 0) return [...seen].join(' ')
  }
  return toErrorMessage(error)
}

/** /real-estate/owner — seller onboarding, dashboard and listing management. */
export function OwnerWorkspacePage() {
  const { t } = useTranslation()
  const load = async (signal: AbortSignal): Promise<Loaded> => {
    const seller = await realEstateApi.getMySeller(signal).catch((e: unknown) => {
      if (e instanceof ApiError && e.status === 404) return null
      throw e
    })
    return [seller, await reference.listGovernorates(undefined, signal)]
  }
  return (
    <Container width="xl">
      <AsyncPage load={load}>
        {([seller, governorates], reload) =>
          seller ? (
            <Workspace seller={seller} governorates={governorates} reload={reload} />
          ) : (
            <Container width="md" style={{ paddingInline: 0 }}>
              <PageHeader
                eyebrow={<><Icon name="home" size={16} />{t('modules.realEstate')}</>}
                title={t('realEstateOwner.onboardingTitle')}
                description={t('realEstateOwner.onboardingIntro')}
              />
              <div className="card-block" data-testid="seller-onboarding">
                <SellerForm seller={null} onSaved={reload} />
              </div>
            </Container>
          )
        }
      </AsyncPage>
    </Container>
  )
}

function Workspace({ seller, governorates, reload }: { seller: RealEstateSeller; governorates: Governorate[]; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const dashboard = useAsyncData((signal) => realEstateApi.getOwnerDashboard(signal), [])
  const listings = useAsyncData((signal) => realEstateApi.listMyListings(page, signal), [page])
  const [editing, setEditing] = useState<OwnerListing | null>(null)
  const [error, setError] = useState<string | null>(null)
  const activeGovernorates = new Set(governorates.map((g) => g.id))
  const refresh = () => {
    dashboard.reload()
    listings.reload()
  }

  return (
    <>
      <PageHeader
        eyebrow={<><Icon name="home" size={16} />{t('modules.realEstate')}</>}
        title={seller.display_name}
        description={t('realEstateOwner.intro')}
        actions={<Badge tone="outline">{t(`sellerTypes.${seller.seller_type}`)}</Badge>}
      />
      <PageStack>
        <SectionCard title={t('realEstateOwner.dashboard')} headingLevel={2}>
          {dashboard.loading ? (
            <LoadingState testId="owner-dashboard-loading" />
          ) : dashboard.error ? (
            <ErrorState error={dashboard.error} onRetry={dashboard.reload} />
          ) : dashboard.data ? (
            <div className="grid-2" data-testid="owner-dashboard">
              <StatCard label={t('realEstateOwner.stats.total')} value={<span data-testid="stat-total">{dashboard.data.listings_total}</span>} />
              <StatCard label={t('realEstateOwner.stats.draft')} value={<span data-testid="stat-draft">{dashboard.data.listings_draft}</span>} />
              <StatCard label={t('realEstateOwner.stats.published')} value={<span data-testid="stat-published">{dashboard.data.listings_published}</span>} />
              <StatCard label={t('realEstateOwner.stats.visible')} value={<span data-testid="stat-visible">{dashboard.data.listings_visible}</span>} hint={t('realEstateOwner.stats.visibleHint')} />
              <StatCard label={t('realEstateOwner.stats.expired')} value={<span data-testid="stat-expired">{dashboard.data.listings_expired}</span>} hint={t('realEstateOwner.stats.expiredHint')} />
              <StatCard label={t('realEstateOwner.stats.sale')} value={<span data-testid="stat-sale">{dashboard.data.listings_sale}</span>} />
              <StatCard label={t('realEstateOwner.stats.rent')} value={<span data-testid="stat-rent">{dashboard.data.listings_rent}</span>} />
            </div>
          ) : null}
        </SectionCard>

        <SectionCard title={editing ? t('realEstateOwner.editListing') : t('realEstateOwner.newListing')} headingLevel={2}>
          <ListingForm
            key={editing?.id ?? 'new'}
            listing={editing}
            governorates={governorates}
            onSaved={() => {
              setEditing(null)
              refresh()
            }}
            onCancel={editing ? () => setEditing(null) : undefined}
          />
        </SectionCard>

        <SectionCard title={t('realEstateOwner.myListings')} headingLevel={2}>
          {error ? <Alert kind="error">{error}</Alert> : null}
          {listings.loading ? (
            <LoadingState testId="owner-listings-loading" />
          ) : listings.error ? (
            <ErrorState error={listings.error} onRetry={listings.reload} />
          ) : (listings.data?.results ?? []).length === 0 ? (
            <EmptyState icon="home" title={t('realEstateOwner.noListings')} testId="owner-listings-empty" />
          ) : (
            <ul className="stack" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {(listings.data?.results ?? []).map((listing) => {
                const published = listing.publication_status === 'PUBLISHED'
                const gaps = published ? [] : publicationGaps(listing, activeGovernorates)
                return (
                  <li key={listing.id} className="card-block" data-testid="owner-listing">
                    <div className="cluster">
                      <strong>{listing.title}</strong>
                      <Badge tone={listing.transaction_type === 'SALE' ? 'brand' : 'success'}>{t(`transactionTypes.${listing.transaction_type}`)}</Badge>
                      <Badge tone="outline">{t(`propertyTypes.${listing.property_type}`)}</Badge>
                      <Badge tone={published ? 'success' : 'neutral'} >{t(`publicationStatus.${listing.publication_status}`)}</Badge>
                      {listing.is_expired ? <Badge tone="warning">{t('realEstateOwner.expired')}</Badge> : null}
                      {listing.is_public ? <Badge tone="brand">{t('realEstateOwner.visible')}</Badge> : null}
                    </div>
                    <div className="text-caption">
                      {name(listing.governorate)}
                      {listing.city ? ` · ${name(listing.city)}` : ''}
                      {listing.district ? ` · ${listing.district}` : ''}
                    </div>
                    <div className="text-secondary" dir="auto">
                      {listing.area_sqm !== null ? `${formatArea(listing.area_sqm, i18n.language)} ${t('realEstate.sqm')} · ` : ''}
                      {formatListingPrice(listing, i18n.language, t('realEstate.priceOnRequest'))}
                    </div>
                    <div className="text-caption" data-testid="owner-listing-expiry">
                      {listing.expires_at
                        ? t('realEstateOwner.expiresOn', { date: new Date(listing.expires_at).toLocaleDateString(i18n.language) })
                        : t('realEstateOwner.noExpiry')}
                    </div>
                    {listing.is_expired ? <Alert kind="warning">{t('realEstateOwner.expiredHint')}</Alert> : null}
                    {gaps.length > 0 ? (
                      <p className="text-caption" data-testid="owner-listing-gaps">
                        {t('realEstateOwner.notReady', { missing: gaps.map((gap) => t(`realEstateOwner.missing.${gap}`)).join(' · ') })}
                      </p>
                    ) : null}
                    <div className="cluster" style={{ marginBlockStart: 'var(--space-2)' }}>
                      <Button variant="ghost" size="sm" onClick={() => setEditing(listing)} leading={<Icon name="edit" size={16} />}>
                        {t('realEstateOwner.edit')}
                      </Button>
                      {published ? (
                        <ApiActionButton size="sm" variant="secondary" action={() => realEstateApi.setMyListingPublished(listing.id, false)} onSuccess={() => { setError(null); refresh() }} onError={(e) => setError(refusalMessage(e, t))} pendingLabel={t('realEstateOwner.unpublishing')}>
                          {t('realEstateOwner.unpublish')}
                        </ApiActionButton>
                      ) : gaps.length === 0 ? (
                        // Guidance only: the backend gate decides, and its typed refusal is shown if it says no.
                        <ApiActionButton size="sm" action={() => realEstateApi.setMyListingPublished(listing.id, true)} onSuccess={() => { setError(null); refresh() }} onError={(e) => setError(refusalMessage(e, t))} pendingLabel={t('realEstateOwner.publishing')}>
                          {t('realEstateOwner.publish')}
                        </ApiActionButton>
                      ) : null}
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
          {listings.data ? (
            <Pagination
              page={page}
              total={Math.max(1, Math.ceil(listings.data.count / PAGE_SIZE))}
              hasNext={listings.data.next !== null}
              hasPrevious={listings.data.previous !== null}
              onChange={(next) => setParams(next > 1 ? { page: String(next) } : {})}
            />
          ) : null}
        </SectionCard>

        <SectionCard title={t('realEstateOwner.profile')} headingLevel={2}>
          <SellerForm seller={seller} onSaved={reload} />
        </SectionCard>
      </PageStack>
    </>
  )
}

function SellerForm({ seller, onSaved }: { seller: RealEstateSeller | null; onSaved: () => void }) {
  const { t } = useTranslation()
  const [f, setF] = useState({
    seller_type: (seller?.seller_type ?? '') as SellerType | '',
    display_name: seller?.display_name ?? '',
    about: seller?.about ?? '',
    phone: seller?.phone ?? '',
    public_email: seller?.public_email ?? '',
  })
  const errors = useFormErrors(['seller_type', 'display_name', 'about', 'phone', 'public_email'] as const)
  const set = (key: keyof typeof f, value: string) => setF((prev) => ({ ...prev, [key]: value }))
  const submit = async () => {
    const next: Record<string, string> = {}
    if (!f.seller_type) next.seller_type = t('validation.required')
    if (!f.display_name.trim()) next.display_name = t('validation.required')
    if (Object.keys(next).length) {
      errors.setFieldErrors(next)
      throw new ClientValidationError()
    }
    const payload = { seller_type: f.seller_type as SellerType, display_name: f.display_name.trim(), about: f.about.trim(), phone: f.phone, public_email: f.public_email }
    return seller ? realEstateApi.updateMySeller(payload) : realEstateApi.createMySeller(payload)
  }
  return (
    <form noValidate onSubmit={(e) => e.preventDefault()}>
      {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
      <div className="grid-2">
        <Select label={t('realEstateOwner.sellerType')} value={f.seller_type} onChange={(e) => set('seller_type', e.target.value)} error={errors.fieldErrors.seller_type} required>
          <option value="">{t('realEstateOwner.chooseSellerType')}</option>
          {SELLER_TYPES.map((code) => (
            <option key={code} value={code}>
              {t(`sellerTypes.${code}`)}
            </option>
          ))}
        </Select>
        <TextField label={t('realEstateOwner.displayName')} value={f.display_name} onChange={(e) => set('display_name', e.target.value)} error={errors.fieldErrors.display_name} required />
      </div>
      <Textarea label={t('realEstateOwner.about')} optional rows={3} value={f.about} onChange={(e) => set('about', e.target.value)} error={errors.fieldErrors.about} />
      <div className="grid-2">
        <TextField label={t('realEstateOwner.phone')} optional dir="ltr" value={f.phone} onChange={(e) => set('phone', e.target.value)} error={errors.fieldErrors.phone} />
        <TextField label={t('realEstateOwner.email')} optional dir="ltr" type="email" value={f.public_email} onChange={(e) => set('public_email', e.target.value)} error={errors.fieldErrors.public_email} />
      </div>
      <FormActions>
        <ApiActionButton type="submit" action={submit} onSuccess={() => onSaved()} onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }} pendingLabel={t('common.saving')}>
          {seller ? t('realEstateOwner.saveProfile') : t('realEstateOwner.createProfile')}
        </ApiActionButton>
      </FormActions>
    </form>
  )
}

const LISTING_FIELDS = [
  'title', 'description', 'property_type', 'transaction_type', 'governorate', 'city', 'district', 'latitude', 'longitude',
  'area_sqm', 'price', 'currency', 'facilities', 'contact_method', 'contact_phone', 'contact_email', 'expires_at', 'suitable_uses',
] as const

function ListingForm({ listing, governorates, onSaved, onCancel }: { listing: OwnerListing | null; governorates: Governorate[]; onSaved: () => void; onCancel?: () => void }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const [f, setF] = useState({
    title: listing?.title ?? '',
    description: listing?.description ?? '',
    property_type: (listing?.property_type ?? '') as PropertyType | '',
    transaction_type: (listing?.transaction_type ?? '') as TransactionType | '',
    governorate: listing?.governorate.id ?? '',
    city: listing?.city?.id ?? '',
    district: listing?.district ?? '',
    latitude: listing?.latitude ?? '',
    longitude: listing?.longitude ?? '',
    area_sqm: listing?.area_sqm ?? '',
    price: listing?.price ?? '',
    currency: listing?.currency ?? 'IQD',
    facilities: listing?.facilities ?? '',
    contact_method: (listing?.contact_method ?? 'PHONE') as ContactMethod,
    contact_phone: listing?.contact_phone ?? '',
    contact_email: listing?.contact_email ?? '',
    expires_at: toLocalInput(listing?.expires_at ?? null),
    suitable_uses: (listing?.suitable_uses ?? []) as SuitableUse[],
  })
  const errors = useFormErrors(LISTING_FIELDS)
  const set = <K extends keyof typeof f>(key: K, value: (typeof f)[K]) => setF((prev) => ({ ...prev, [key]: value }))

  // The reference lists hold ACTIVE rows only. A listing may still reference a governorate or city that an
  // administrator has since deactivated: keep that current value visible (once, labelled), and never offer it
  // as a destination again after the user moves away from it.
  const historicalGovernorate = listing && !governorates.some((g) => g.id === listing.governorate.id) ? listing.governorate : null
  const governorateOptions = historicalGovernorate ? [historicalGovernorate, ...governorates] : governorates
  const cities = useAsyncData<City[]>(
    (signal) => (f.governorate ? reference.listCities(f.governorate, signal) : Promise.resolve([])),
    [f.governorate],
  )
  const currentCity = listing?.city && listing.city.governorate === f.governorate ? listing.city : null
  const cityList = cities.data ?? []
  const historicalCity = currentCity && !cityList.some((c) => c.id === currentCity.id) ? currentCity : null
  const cityOptions = historicalCity ? [historicalCity, ...cityList] : cityList

  const submit = async () => {
    const next: Record<string, string> = {}
    if (!f.title.trim()) next.title = t('validation.required')
    if (!f.property_type) next.property_type = t('validation.required')
    if (!f.transaction_type) next.transaction_type = t('validation.required')
    if (!f.governorate) next.governorate = t('validation.required')
    if (f.price !== '' && (Number.isNaN(Number(f.price)) || Number(f.price) < 0)) next.price = t('realEstateOwner.invalidPrice')
    if (f.area_sqm !== '' && (Number.isNaN(Number(f.area_sqm)) || Number(f.area_sqm) <= 0)) next.area_sqm = t('realEstateOwner.invalidArea')
    if ((f.latitude === '') !== (f.longitude === '')) next.latitude = t('realEstateOwner.coordinatePair')
    if (Object.keys(next).length) {
      errors.setFieldErrors(next)
      throw new ClientValidationError()
    }
    const payload: ListingWrite = {
      title: f.title.trim(),
      description: f.description.trim(),
      property_type: f.property_type as PropertyType,
      transaction_type: f.transaction_type as TransactionType,
      district: f.district.trim(),
      latitude: f.latitude === '' ? null : f.latitude,
      longitude: f.longitude === '' ? null : f.longitude,
      area_sqm: f.area_sqm === '' ? null : f.area_sqm,
      price: f.price === '' ? null : f.price,
      currency: f.currency,
      facilities: f.facilities.trim(),
      contact_method: f.contact_method,
      contact_phone: f.contact_phone.trim(),
      contact_email: f.contact_email.trim(),
      expires_at: fromLocalInput(f.expires_at),
      suitable_uses: f.suitable_uses,
    }
    // Reference rows are validated against the ACTIVE lists: an unchanged (possibly deactivated) governorate or
    // city is simply not sent, so saving other edits is never refused for a value the user did not touch.
    if (!listing || f.governorate !== listing.governorate.id) payload.governorate = f.governorate
    if (!listing || (f.city || null) !== (listing.city?.id ?? null)) payload.city = f.city || null
    return listing ? realEstateApi.updateMyListing(listing.id, payload) : realEstateApi.createMyListing(payload)
  }

  const toggleUse = (use: SuitableUse) =>
    set('suitable_uses', f.suitable_uses.includes(use) ? f.suitable_uses.filter((u) => u !== use) : [...f.suitable_uses, use])

  return (
    <form noValidate onSubmit={(e) => e.preventDefault()} data-testid="listing-form">
      {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
      <p className="text-caption">{t('realEstateOwner.draftNote')}</p>
      {listing?.publication_status === 'PUBLISHED' ? <Alert kind="info">{t('realEstateOwner.publishedEditNote')}</Alert> : null}
      <TextField label={t('realEstateOwner.title')} value={f.title} onChange={(e) => set('title', e.target.value)} error={errors.fieldErrors.title} required />
      <div className="grid-2">
        <Select label={t('realEstate.propertyType')} value={f.property_type} onChange={(e) => set('property_type', e.target.value as PropertyType | '')} error={errors.fieldErrors.property_type} required>
          <option value="">{t('realEstateOwner.choosePropertyType')}</option>
          {PROPERTY_TYPES.map((code) => (
            <option key={code} value={code}>
              {t(`propertyTypes.${code}`)}
            </option>
          ))}
        </Select>
        <Select label={t('realEstate.transaction')} value={f.transaction_type} onChange={(e) => set('transaction_type', e.target.value as TransactionType | '')} error={errors.fieldErrors.transaction_type} required>
          <option value="">{t('realEstateOwner.chooseTransaction')}</option>
          {TRANSACTION_TYPES.map((code) => (
            <option key={code} value={code}>
              {t(`transactionTypes.${code}`)}
            </option>
          ))}
        </Select>
      </div>
      <Textarea label={t('realEstateOwner.description')} optional rows={3} value={f.description} onChange={(e) => set('description', e.target.value)} error={errors.fieldErrors.description} />
      <div className="grid-2">
        <Select
          label={t('realEstate.governorate')}
          value={f.governorate}
          onChange={(e) => setF((prev) => ({ ...prev, governorate: e.target.value, city: '' }))}
          error={errors.fieldErrors.governorate}
          required
        >
          <option value="">{t('realEstateOwner.chooseGovernorate')}</option>
          {governorateOptions.map((g) => (
            <option key={g.id} value={g.id} disabled={g === historicalGovernorate && f.governorate !== g.id}>
              {g === historicalGovernorate ? t('realEstateOwner.currentUnavailable', { name: name(g) }) : name(g)}
            </option>
          ))}
        </Select>
        <Select
          label={t('realEstate.city')}
          optional
          adornment={cities.loading && f.governorate ? <Spinner size="sm" /> : null}
          value={f.city}
          disabled={!f.governorate}
          onChange={(e) => set('city', e.target.value)}
          error={errors.fieldErrors.city}
        >
          <option value="">{t('realEstateOwner.noCity')}</option>
          {cityOptions.map((c) => (
            <option key={c.id} value={c.id} disabled={c === historicalCity && f.city !== c.id}>
              {c === historicalCity && !cities.loading ? t('realEstateOwner.currentUnavailable', { name: name(c) }) : name(c)}
            </option>
          ))}
        </Select>
      </div>
      <TextField label={t('realEstateOwner.district')} optional value={f.district} onChange={(e) => set('district', e.target.value)} error={errors.fieldErrors.district} />
      <div className="grid-2">
        <TextField label={t('realEstateOwner.latitude')} optional dir="ltr" inputMode="decimal" value={f.latitude} onChange={(e) => set('latitude', e.target.value)} error={errors.fieldErrors.latitude} />
        <TextField label={t('realEstateOwner.longitude')} optional dir="ltr" inputMode="decimal" value={f.longitude} onChange={(e) => set('longitude', e.target.value)} error={errors.fieldErrors.longitude} />
      </div>
      <div className="grid-2">
        <TextField label={t('realEstate.area')} optional dir="ltr" inputMode="decimal" hint={t('realEstateOwner.areaHint')} value={f.area_sqm} onChange={(e) => set('area_sqm', e.target.value)} error={errors.fieldErrors.area_sqm} />
        <TextField label={t('realEstate.price')} optional dir="ltr" inputMode="decimal" hint={t('realEstateOwner.priceHint')} value={f.price} onChange={(e) => set('price', e.target.value)} error={errors.fieldErrors.price} />
      </div>
      <Select label={t('realEstateOwner.currency')} value={f.currency} onChange={(e) => set('currency', e.target.value)} error={errors.fieldErrors.currency}>
        <option value="IQD">IQD</option>
        <option value="USD">USD</option>
      </Select>
      <CheckboxGroup legend={t('realEstate.suitableUse')} error={errors.fieldErrors.suitable_uses}>
        {SUITABLE_USES.map((use) => (
          <Checkbox key={use} label={t(`suitableUses.${use}`)} checked={f.suitable_uses.includes(use)} onChange={() => toggleUse(use)} />
        ))}
      </CheckboxGroup>
      <Textarea label={t('realEstate.facilities')} optional rows={2} value={f.facilities} onChange={(e) => set('facilities', e.target.value)} error={errors.fieldErrors.facilities} />
      <div className="grid-2">
        <Select label={t('realEstateOwner.contactMethod')} value={f.contact_method} onChange={(e) => set('contact_method', e.target.value as ContactMethod)} error={errors.fieldErrors.contact_method}>
          {CONTACT_METHODS.map((code) => (
            <option key={code} value={code}>
              {t(`contactMethods.${code}`)}
            </option>
          ))}
        </Select>
        <TextField label={t('realEstateOwner.expiresAt')} optional type="datetime-local" dir="ltr" hint={t('realEstateOwner.expiresHint')} value={f.expires_at} onChange={(e) => set('expires_at', e.target.value)} error={errors.fieldErrors.expires_at} />
      </div>
      <div className="grid-2">
        <TextField label={t('realEstateOwner.contactPhone')} optional dir="ltr" value={f.contact_phone} onChange={(e) => set('contact_phone', e.target.value)} error={errors.fieldErrors.contact_phone} />
        <TextField label={t('realEstateOwner.contactEmail')} optional dir="ltr" type="email" value={f.contact_email} onChange={(e) => set('contact_email', e.target.value)} error={errors.fieldErrors.contact_email} />
      </div>
      <FormActions>
        {onCancel ? (
          <Button variant="ghost" onClick={onCancel}>
            {t('realEstateOwner.cancel')}
          </Button>
        ) : null}
        <ApiActionButton type="submit" action={submit} onSuccess={() => onSaved()} onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }} pendingLabel={t('common.saving')}>
          {listing ? t('realEstateOwner.saveListing') : t('realEstateOwner.createListing')}
        </ApiActionButton>
      </FormActions>
    </form>
  )
}
