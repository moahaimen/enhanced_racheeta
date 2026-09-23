import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'

import { providers as providersApi, reference, PROVIDER_TYPES } from '../../api'
import type { City, Governorate, ProviderCard, ProviderKind, ProviderType, Specialty } from '../../api'
import { AsyncPage, Spinner } from '../../components'
import { useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { ProviderTypeBadge } from './ProviderBadges'

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
    <>
      <section className="card">
        <h2>{t('providers.title')}</h2>
        <p className="muted">{t('providers.intro')}</p>
        <AsyncPage
          load={(signal) =>
            Promise.all([reference.listGovernorates(undefined, signal), reference.listSpecialties(signal)])
          }
          loadingLabel={t('providers.loadingFilters')}
        >
          {([governorates, specialties]) => (
            <FilterBar
              filters={filters}
              governorates={governorates}
              specialties={specialties}
              onChange={update}
            />
          )}
        </AsyncPage>
      </section>
      <section className="card">
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
          deps={[
            filters.type,
            filters.kind,
            filters.specialty,
            filters.governorate,
            filters.city,
            filters.search,
            filters.page,
          ]}
          loadingLabel={t('providers.loading')}
        >
          {(page) => (
            <>
              <p className="muted" data-testid="results-count">
                {t('providers.results', { count: page.count })}
              </p>
              {page.results.length === 0 ? (
                <p className="async-state" data-testid="providers-empty">
                  {t('providers.empty')}
                </p>
              ) : (
                <ul className="provider-grid" aria-label={t('providers.title')}>
                  {page.results.map((provider) => (
                    <li key={provider.id}>
                      <ProviderCardView provider={provider} />
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
    </>
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
  const cities = useAsyncData<City[]>(
    (signal) => (filters.governorate ? reference.listCities(filters.governorate, signal) : Promise.resolve([])),
    [filters.governorate],
  )

  return (
    <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label={t('providers.filters')}>
      <label className="filters__item">
        <span>{t('providers.type')}</span>
        <select value={filters.type} onChange={(e) => onChange({ type: e.target.value as ProviderType | '' })}>
          <option value="">{t('common.all')}</option>
          {PROVIDER_TYPES.map((code) => (
            <option key={code} value={code}>
              {t(`providerTypes.${code}`)}
            </option>
          ))}
        </select>
      </label>
      <label className="filters__item">
        <span>{t('providers.specialty')}</span>
        <select value={filters.specialty} onChange={(e) => onChange({ specialty: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {specialties.map((s) => (
            <option key={s.id} value={s.slug}>
              {name(s)}
            </option>
          ))}
        </select>
      </label>
      <label className="filters__item">
        <span>{t('providers.governorate')}</span>
        <select value={filters.governorate} onChange={(e) => onChange({ governorate: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {governorates.map((g) => (
            <option key={g.id} value={g.id}>
              {name(g)}
            </option>
          ))}
        </select>
      </label>
      <label className="filters__item">
        <span>
          {t('providers.city')} {cities.loading && filters.governorate ? <Spinner size="sm" /> : null}
        </span>
        <select
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
        </select>
      </label>
      <label className="filters__item filters__item--grow">
        <span>{t('common.search')}</span>
        <input
          type="search"
          placeholder={t('providers.searchPlaceholder')}
          defaultValue={filters.search}
          onKeyDown={(e) => {
            if (e.key === 'Enter') onChange({ search: (e.target as HTMLInputElement).value.trim() })
          }}
          onBlur={(e) => {
            if (e.target.value.trim() !== filters.search) onChange({ search: e.target.value.trim() })
          }}
        />
      </label>
      <button
        type="button"
        className="btn btn--ghost"
        onClick={() => onChange({ type: '', kind: '', specialty: '', governorate: '', city: '', search: '' })}
      >
        {t('common.clear')}
      </button>
    </form>
  )
}

export function ProviderCardView({ provider }: { provider: ProviderCard }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  return (
    <article className="provider-card">
      {provider.image_url ? (
        <img className="provider-card__image" src={provider.image_url} alt="" loading="lazy" />
      ) : (
        <div className="provider-card__image provider-card__image--placeholder" aria-hidden="true" />
      )}
      <div className="provider-card__body">
        <h3 className="provider-card__title">
          <Link to={`/providers/${provider.id}`}>{provider.display_name}</Link>
        </h3>
        <ProviderTypeBadge type={provider.provider_type} />
        <p className="muted">
          {name(provider.governorate)}
          {provider.city ? ` — ${name(provider.city)}` : ''}
        </p>
        {provider.specialties.length > 0 ? (
          <ul className="chips" aria-label={t('providers.specialty')}>
            {provider.specialties.map((s) => (
              <li key={s.id} className="chip">
                {name(s)}
              </li>
            ))}
          </ul>
        ) : null}
        <Link to={`/providers/${provider.id}`} className="link">
          {t('providers.viewProfile')}
        </Link>
      </div>
    </article>
  )
}

function Pagination({
  page,
  total,
  hasNext,
  hasPrevious,
  onChange,
}: {
  page: number
  total: number
  hasNext: boolean
  hasPrevious: boolean
  onChange: (page: number) => void
}) {
  const { t } = useTranslation()
  if (total <= 1) return null
  return (
    <nav className="pagination" aria-label="pagination">
      <button type="button" className="btn btn--ghost" disabled={!hasPrevious} onClick={() => onChange(page - 1)}>
        {t('common.previous')}
      </button>
      <span>{t('common.page', { page, total })}</span>
      <button type="button" className="btn btn--ghost" disabled={!hasNext} onClick={() => onChange(page + 1)}>
        {t('common.next')}
      </button>
    </nav>
  )
}
