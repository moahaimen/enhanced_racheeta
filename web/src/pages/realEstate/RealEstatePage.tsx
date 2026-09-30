import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'

import { LISTING_ORDERINGS, PROPERTY_TYPES, SUITABLE_USES, TRANSACTION_TYPES, realEstate as realEstateApi, reference } from '../../api'
import type { City, Governorate, ListingOrdering, PropertyListing, PropertyType, SuitableUse, TransactionType } from '../../api'
import {
  AsyncPage,
  Badge,
  Button,
  Container,
  EmptyState,
  Icon,
  PageHeader,
  PageStack,
  Pagination,
  SearchField,
  SectionCard,
  Select,
  Spinner,
  TextField,
} from '../../design-system'
import { useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { formatArea, formatListingPrice } from './realEstateFormat'
import styles from './RealEstate.module.css'

const PAGE_SIZE = 20

interface Filters {
  transaction_type: TransactionType | ''
  property_type: PropertyType | ''
  governorate: string
  city: string
  suitable_use: SuitableUse | ''
  min_price: string
  max_price: string
  min_area: string
  max_area: string
  search: string
  ordering: ListingOrdering | ''
  page: number
}

const TEXT_FILTERS = ['search', 'min_price', 'max_price', 'min_area', 'max_area'] as const

function readFilters(params: URLSearchParams): Filters {
  const get = (key: string) => params.get(key) ?? ''
  return {
    transaction_type: get('transaction_type') as Filters['transaction_type'],
    property_type: get('property_type') as Filters['property_type'],
    governorate: get('governorate'),
    city: get('city'),
    suitable_use: get('suitable_use') as Filters['suitable_use'],
    min_price: get('min_price'),
    max_price: get('max_price'),
    min_area: get('min_area'),
    max_area: get('max_area'),
    search: get('search'),
    ordering: get('ordering') as Filters['ordering'],
    page: Math.max(1, Number(params.get('page') ?? '1') || 1),
  }
}

/**
 * /real-estate — the public medical real-estate catalogue. Every filter, the
 * ordering and the pagination are sent to the BACKEND, which decides what is
 * visible; nothing is filtered or sorted here.
 */
export function RealEstatePage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const filters = readFilters(params)

  const update = (patch: Partial<Filters>) => {
    const next = { ...filters, ...patch }
    if (patch.page === undefined) next.page = 1
    if (patch.governorate !== undefined && patch.governorate !== filters.governorate) next.city = ''
    const out = new URLSearchParams()
    for (const [key, value] of Object.entries(next)) {
      if (value === '' || value === 1 || value === undefined) continue
      out.set(key, String(value))
    }
    setParams(out)
  }

  return (
    <Container width="xl">
      <PageHeader
        eyebrow={
          <>
            <Icon name="home" size={16} />
            {t('modules.realEstate')}
          </>
        }
        title={t('realEstate.title')}
        description={t('realEstate.intro')}
      />
      <PageStack>
        <SectionCard title={t('realEstate.filters')} headingLevel={2}>
          <AsyncPage
            load={(signal) => reference.listGovernorates(undefined, signal)}
            skeleton={
              <div className="cluster">
                <Spinner size="sm" /> <span className="text-muted">{t('realEstate.loadingFilters')}</span>
              </div>
            }
          >
            {(governorates) => <FilterBar filters={filters} governorates={governorates} onChange={update} />}
          </AsyncPage>
        </SectionCard>

        <section aria-label={t('realEstate.results')}>
          <AsyncPage
            load={(signal) => realEstateApi.listListings({ ...filters, page: filters.page }, signal)}
            deps={[
              filters.transaction_type,
              filters.property_type,
              filters.governorate,
              filters.city,
              filters.suitable_use,
              filters.min_price,
              filters.max_price,
              filters.min_area,
              filters.max_area,
              filters.search,
              filters.ordering,
              filters.page,
            ]}
            loadingLabel={t('realEstate.loading')}
          >
            {(page) => (
              <>
                <p className="text-secondary" data-testid="realestate-count">
                  {t('realEstate.resultsCount', { count: page.count })}
                </p>
                {page.results.length === 0 ? (
                  <div className="card-block">
                    <EmptyState
                      icon="home"
                      title={t('realEstate.empty')}
                      testId="realestate-empty"
                      action={
                        <Button
                          variant="secondary"
                          onClick={() =>
                            update({ transaction_type: '', property_type: '', governorate: '', city: '', suitable_use: '', min_price: '', max_price: '', min_area: '', max_area: '', search: '', ordering: '' })
                          }
                        >
                          {t('common.clear')}
                        </Button>
                      }
                    />
                  </div>
                ) : (
                  <ul className="stack" data-testid="realestate-results" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                    {page.results.map((listing) => (
                      <li key={listing.id}>
                        <ListingCard listing={listing} />
                      </li>
                    ))}
                  </ul>
                )}
                <Pagination
                  page={filters.page}
                  total={Math.max(1, Math.ceil(page.count / PAGE_SIZE))}
                  hasNext={page.next !== null}
                  hasPrevious={page.previous !== null}
                  onChange={(next) => update({ page: next })}
                />
              </>
            )}
          </AsyncPage>
        </section>
      </PageStack>
    </Container>
  )
}

function ListingCard({ listing }: { listing: PropertyListing }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  return (
    <article className="card-block" data-testid="realestate-listing">
      <div className="cluster">
        <Link to={`/real-estate/${listing.id}`}>
          <strong>{listing.title}</strong>
        </Link>
        <Badge tone={listing.transaction_type === 'SALE' ? 'brand' : 'success'}>{t(`transactionTypes.${listing.transaction_type}`)}</Badge>
        <Badge tone="outline">{t(`propertyTypes.${listing.property_type}`)}</Badge>
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
      <div className={styles.uses} data-testid="realestate-uses">
        {listing.suitable_uses.map((use) => (
          <Badge key={use} tone="neutral">
            {t(`suitableUses.${use}`)}
          </Badge>
        ))}
      </div>
    </article>
  )
}

function FilterBar({ filters, governorates, onChange }: { filters: Filters; governorates: Governorate[]; onChange: (patch: Partial<Filters>) => void }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  // The URL is the source of truth. `draft` only holds what is being typed in the free-text and
  // numeric fields; whenever the applied values change (Back/Forward, chip, Clear, deep link) it is re-derived.
  const appliedKey = TEXT_FILTERS.map((key) => filters[key]).join('|')
  const [draft, setDraft] = useState(() => Object.fromEntries(TEXT_FILTERS.map((key) => [key, filters[key]])) as Record<(typeof TEXT_FILTERS)[number], string>)
  const [applied, setApplied] = useState(appliedKey)
  if (applied !== appliedKey) {
    setApplied(appliedKey)
    setDraft(Object.fromEntries(TEXT_FILTERS.map((key) => [key, filters[key]])) as Record<(typeof TEXT_FILTERS)[number], string>)
  }
  const cities = useAsyncData<City[]>(
    (signal) => (filters.governorate ? reference.listCities(filters.governorate, signal) : Promise.resolve([])),
    [filters.governorate],
  )
  const setText = (key: (typeof TEXT_FILTERS)[number], value: string) => setDraft((prev) => ({ ...prev, [key]: value }))

  const submit = (event: FormEvent) => {
    event.preventDefault()
    onChange({
      search: draft.search.trim(),
      min_price: draft.min_price.trim(),
      max_price: draft.max_price.trim(),
      min_area: draft.min_area.trim(),
      max_area: draft.max_area.trim(),
    })
  }

  return (
    <form onSubmit={submit} aria-label={t('realEstate.filters')}>
      <SearchField label={t('common.search')} placeholder={t('realEstate.searchPlaceholder')} value={draft.search} onChange={(e) => setText('search', e.target.value)} />
      <div className={styles.filters}>
        <Select label={t('realEstate.transaction')} value={filters.transaction_type} onChange={(e) => onChange({ transaction_type: e.target.value as Filters['transaction_type'] })}>
          <option value="">{t('common.all')}</option>
          {TRANSACTION_TYPES.map((code) => (
            <option key={code} value={code}>
              {t(`transactionTypes.${code}`)}
            </option>
          ))}
        </Select>
        <Select label={t('realEstate.propertyType')} value={filters.property_type} onChange={(e) => onChange({ property_type: e.target.value as Filters['property_type'] })}>
          <option value="">{t('common.all')}</option>
          {PROPERTY_TYPES.map((code) => (
            <option key={code} value={code}>
              {t(`propertyTypes.${code}`)}
            </option>
          ))}
        </Select>
        <Select label={t('realEstate.suitableUse')} value={filters.suitable_use} onChange={(e) => onChange({ suitable_use: e.target.value as Filters['suitable_use'] })}>
          <option value="">{t('common.all')}</option>
          {SUITABLE_USES.map((code) => (
            <option key={code} value={code}>
              {t(`suitableUses.${code}`)}
            </option>
          ))}
        </Select>
        <Select label={t('realEstate.governorate')} value={filters.governorate} onChange={(e) => onChange({ governorate: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {governorates.map((g) => (
            <option key={g.id} value={g.id}>
              {name(g)}
            </option>
          ))}
        </Select>
        <Select
          label={t('realEstate.city')}
          adornment={cities.loading && filters.governorate ? <Spinner size="sm" /> : null}
          value={filters.city}
          disabled={!filters.governorate || cities.loading}
          onChange={(e) => onChange({ city: e.target.value })}
        >
          <option value="">{t('common.all')}</option>
          {(cities.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {name(c)}
            </option>
          ))}
        </Select>
        <Select label={t('realEstate.ordering')} value={filters.ordering} onChange={(e) => onChange({ ordering: e.target.value as Filters['ordering'] })}>
          <option value="">{t('realEstate.orderings.-created_at')}</option>
          {LISTING_ORDERINGS.filter((o) => o !== '-created_at').map((code) => (
            <option key={code} value={code}>
              {t(`realEstate.orderings.${code}`)}
            </option>
          ))}
        </Select>
        <TextField label={t('realEstate.minPrice')} dir="ltr" inputMode="decimal" value={draft.min_price} onChange={(e) => setText('min_price', e.target.value)} />
        <TextField label={t('realEstate.maxPrice')} dir="ltr" inputMode="decimal" value={draft.max_price} onChange={(e) => setText('max_price', e.target.value)} />
        <TextField label={t('realEstate.minArea')} dir="ltr" inputMode="decimal" value={draft.min_area} onChange={(e) => setText('min_area', e.target.value)} />
        <TextField label={t('realEstate.maxArea')} dir="ltr" inputMode="decimal" value={draft.max_area} onChange={(e) => setText('max_area', e.target.value)} />
      </div>
      <div className={styles.actions}>
        <Button type="submit" leading={<Icon name="search" size={18} />}>
          {t('common.search')}
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => onChange({ transaction_type: '', property_type: '', governorate: '', city: '', suitable_use: '', min_price: '', max_price: '', min_area: '', max_area: '', search: '', ordering: '' })}
        >
          {t('common.clear')}
        </Button>
      </div>
    </form>
  )
}
