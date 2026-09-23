import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { providers as providersApi, reference, PROVIDER_TYPES } from '../../api'
import type { City, Governorate, ProviderKind, ProviderType, Specialty } from '../../api'
import {
  AsyncPage,
  Button,
  Container,
  EmptyState,
  Icon,
  PageStack,
  Pagination,
  ProviderCard,
  ProviderCardSkeleton,
  SearchField,
  Select,
  Spinner,
} from '../../design-system'
import { useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import styles from './ProvidersPage.module.css'

const PAGE_SIZE = 12

interface Filters {
  type: ProviderType | ''
  kind: ProviderKind | ''
  specialty: string
  governorate: string
  city: string
  search: string
  page: number
}

function readFilters(params: URLSearchParams): Filters {
  return {
    type: (params.get('type') as ProviderType | null) ?? '',
    kind: (params.get('kind') as ProviderKind | null) ?? '',
    specialty: params.get('specialty') ?? '',
    governorate: params.get('governorate') ?? '',
    city: params.get('city') ?? '',
    search: params.get('search') ?? '',
    page: Math.max(1, Number(params.get('page') ?? '1') || 1),
  }
}

/** Public provider search. Filters live in the URL so results are shareable. */
export function ProvidersPage() {
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
      <PageStack>
        <section className={styles.hero} aria-labelledby="providers-title">
          <h1 id="providers-title">{t('providers.title')}</h1>
          <p>{t('providers.intro')}</p>
        </section>

        <section className="card-block" aria-labelledby="filters-title">
          <h2 id="filters-title" className="visually-hidden">
            {t('providers.filters')}
          </h2>
          <AsyncPage
            load={(signal) => Promise.all([reference.listGovernorates(undefined, signal), reference.listSpecialties(signal)])}
            skeleton={
              <div className="cluster">
                <Spinner size="sm" /> <span className="text-muted">{t('providers.loadingFilters')}</span>
              </div>
            }
          >
            {([governorates, specialties]) => (
              <FilterBar filters={filters} governorates={governorates} specialties={specialties} onChange={update} />
            )}
          </AsyncPage>
        </section>

        <section aria-labelledby="results-title">
          <h2 id="results-title" className="visually-hidden">
            {t('providers.results_other', { count: 0 })}
          </h2>
          <AsyncPage
            load={(signal) =>
              providersApi.listProviders(
                {
                  type: filters.type,
                  kind: filters.kind,
                  specialty: filters.specialty,
                  governorate: filters.governorate,
                  city: filters.city,
                  search: filters.search,
                  page: filters.page,
                  page_size: PAGE_SIZE,
                },
                signal,
              )
            }
            deps={[filters.type, filters.kind, filters.specialty, filters.governorate, filters.city, filters.search, filters.page]}
            loadingLabel={t('providers.loading')}
            skeleton={
              <div className={styles.grid}>
                {Array.from({ length: 6 }, (_, i) => (
                  <ProviderCardSkeleton key={i} />
                ))}
              </div>
            }
          >
            {(page) => (
              <>
                <ActiveFilters filters={filters} count={page.count} onChange={update} />
                {page.results.length === 0 ? (
                  <div className="card-block">
                    <EmptyState
                      icon="search"
                      title={t('providers.empty')}
                      testId="providers-empty"
                      action={
                        <Button variant="secondary" onClick={() => update({ type: '', kind: '', specialty: '', governorate: '', city: '', search: '' })}>
                          {t('common.clear')}
                        </Button>
                      }
                    />
                  </div>
                ) : (
                  <ul className={styles.grid} aria-label={t('providers.title')} style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                    {page.results.map((provider) => (
                      <li key={provider.id}>
                        <ProviderCard provider={provider} />
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

function FilterBar({
  filters,
  governorates,
  specialties,
  onChange,
}: {
  filters: Filters
  governorates: Governorate[]
  specialties: Specialty[]
  onChange: (patch: Partial<Filters>) => void
}) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  // The URL (filters.search) is the source of truth; `draft` only holds what
  // the user is typing. Whenever the applied value changes (chip removed,
  // Clear, Back/Forward, deep link) the draft is re-derived during render.
  const [draft, setDraft] = useState(filters.search)
  const [applied, setApplied] = useState(filters.search)
  if (applied !== filters.search) {
    setApplied(filters.search)
    setDraft(filters.search)
  }
  const cities = useAsyncData<City[]>(
    (signal) => (filters.governorate ? reference.listCities(filters.governorate, signal) : Promise.resolve([])),
    [filters.governorate],
  )

  const submitSearch = (event: FormEvent) => {
    event.preventDefault()
    onChange({ search: draft.trim() })
  }

  return (
    <form onSubmit={submitSearch} aria-label={t('providers.filters')}>
      <div className={styles.searchRow}>
        <SearchField label={t('common.search')} placeholder={t('providers.searchPlaceholder')} value={draft} onChange={(e) => setDraft(e.target.value)} />
        <Button type="submit" leading={<Icon name="search" size={18} />}>
          {t('common.search')}
        </Button>
      </div>
      <div className={styles.filters}>
        <Select label={t('providers.type')} value={filters.type} onChange={(e) => onChange({ type: e.target.value as ProviderType | '' })}>
          <option value="">{t('common.all')}</option>
          {PROVIDER_TYPES.map((code) => (
            <option key={code} value={code}>
              {t(`providerTypes.${code}`)}
            </option>
          ))}
        </Select>
        <Select label={t('providers.specialty')} value={filters.specialty} onChange={(e) => onChange({ specialty: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {specialties.map((s) => (
            <option key={s.id} value={s.slug}>
              {name(s)}
            </option>
          ))}
        </Select>
        <Select label={t('providers.governorate')} value={filters.governorate} onChange={(e) => onChange({ governorate: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {governorates.map((g) => (
            <option key={g.id} value={g.id}>
              {name(g)}
            </option>
          ))}
        </Select>
        <Select
          label={t('providers.city')}
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
        <Button
          type="button"
          variant="ghost"
          onClick={() => onChange({ type: '', kind: '', specialty: '', governorate: '', city: '', search: '' })}
        >
          {t('common.clear')}
        </Button>
      </div>
    </form>
  )
}

function ActiveFilters({ filters, count, onChange }: { filters: Filters; count: number; onChange: (patch: Partial<Filters>) => void }) {
  const { t } = useTranslation()
  const chips: { key: keyof Filters; label: string }[] = []
  if (filters.type) chips.push({ key: 'type', label: t(`providerTypes.${filters.type}`) })
  if (filters.kind) chips.push({ key: 'kind', label: t(`providerKinds.${filters.kind}`) })
  if (filters.specialty) chips.push({ key: 'specialty', label: `${t('providers.specialty')}: ${filters.specialty}` })
  if (filters.search) chips.push({ key: 'search', label: `“${filters.search}”` })
  if (filters.governorate) chips.push({ key: 'governorate', label: t('providers.governorate') })
  if (filters.city) chips.push({ key: 'city', label: t('providers.city') })
  return (
    <div className={styles.summary} data-testid="results-count">
      <span className={styles.summaryCount}>{t('providers.results', { count })}</span>
      {chips.map((chip) => (
        <button key={chip.key} type="button" className={styles.chipButton} onClick={() => onChange({ [chip.key]: '' } as Partial<Filters>)}>
          {chip.label}
          <Icon name="x" size={14} label={t('common.clear')} />
        </button>
      ))}
    </div>
  )
}
