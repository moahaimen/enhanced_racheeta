import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { DEGREES, EMPLOYMENT_TYPES, jobs as jobsApi, PROFESSIONS, reference, SHIFT_TYPES, WORK_MODES } from '../../api'
import type { City, Governorate, Specialty } from '../../api'
import { useAuth } from '../../auth/useAuth'
import { AsyncPage, Button, Checkbox, Container, EmptyState, Icon, JobCard, JobCardSkeleton, LinkButton, PageStack, Pagination, SearchField, Select, Spinner } from '../../design-system'
import { useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { JOB_FILTER_KEYS, readJobFilters, writeJobFilters } from './filters'
import styles from './JobsPage.module.css'

const PAGE_SIZE = 12

/** Public job search. Filters live in the URL. Only published jobs of verified employers. */
export function JobsPage() {
  const { t } = useTranslation()
  const { status, account } = useAuth()
  const [params, setParams] = useSearchParams()
  const filters = readJobFilters(params)

  const update = (patch: Record<string, string | number | undefined>) => {
    const next: Record<string, string | number | undefined> = { ...filters, ...patch }
    if (patch.page === undefined) next.page = 1
    if (patch.governorate !== undefined && patch.governorate !== filters.governorate) next.city = ''
    setParams(writeJobFilters(next))
  }
  const clear = () => setParams(new URLSearchParams())

  return (
    <Container width="xl">
      <PageStack>
        <section className={styles.hero} aria-labelledby="jobs-title">
          <h1 id="jobs-title">{t('jobsPage.title')}</h1>
          <p>{t('jobsPage.intro')}</p>
          <div className={styles.heroActions}>
            {status === 'authenticated' ? (
              <>
                <LinkButton to="/jobs/profile" variant="secondary" size="sm" leading={<Icon name="user" size={16} />}>
                  {t('nav.seekerProfile')}
                </LinkButton>
                <LinkButton to="/jobs/my-applications" variant="ghost" size="sm">
                  {t('nav.myApplications')}
                </LinkButton>
              </>
            ) : status === 'anonymous' ? (
              <LinkButton to="/register" variant="secondary" size="sm">
                {t('jobsPage.registerCta')}
              </LinkButton>
            ) : null}
            {account?.role !== 'PATIENT' ? (
              <LinkButton to="/employer" variant="ghost" size="sm" leading={<Icon name="briefcase" size={16} />}>
                {t('jobsPage.employerCta')}
              </LinkButton>
            ) : null}
          </div>
        </section>

        <section className="card-block" aria-labelledby="jobs-filters">
          <h2 id="jobs-filters" className="visually-hidden">
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
            {([governorates, specialties]) => <FilterBar filters={filters} governorates={governorates} specialties={specialties} onChange={update} onClear={clear} />}
          </AsyncPage>
        </section>

        <section aria-labelledby="jobs-results">
          <h2 id="jobs-results" className="visually-hidden">
            {t('jobsPage.results_other', { count: 0 })}
          </h2>
          <AsyncPage
            load={(signal) => jobsApi.listJobs({ ...filters, page_size: PAGE_SIZE }, signal)}
            deps={[...JOB_FILTER_KEYS.map((k) => filters[k] ?? ''), filters.page]}
            skeleton={
              <ul className={styles.grid}>
                {Array.from({ length: 6 }, (_, i) => (
                  <li key={i}>
                    <JobCardSkeleton />
                  </li>
                ))}
              </ul>
            }
          >
            {(page) => (
              <>
                <div className={styles.summary} data-testid="jobs-count">
                  <span className={styles.count}>{t('jobsPage.results', { count: page.count })}</span>
                  {JOB_FILTER_KEYS.filter((k) => filters[k]).map((k) => (
                    <button key={k} type="button" className={styles.chip} onClick={() => update({ [k]: '' })}>
                      {t(`jobsPage.filters.${k}`)}
                      <Icon name="x" size={14} label={t('common.clear')} />
                    </button>
                  ))}
                </div>
                {page.results.length === 0 ? (
                  <div className="card-block">
                    <EmptyState icon="briefcase" title={t('jobsPage.empty')} testId="jobs-empty" action={<Button variant="secondary" onClick={clear}>{t('common.clear')}</Button>}>
                      {t('jobsPage.emptyBody')}
                    </EmptyState>
                  </div>
                ) : (
                  <ul className={styles.grid} aria-label={t('jobsPage.title')}>
                    {page.results.map((job) => (
                      <li key={job.id}>
                        <JobCard job={job} />
                      </li>
                    ))}
                  </ul>
                )}
                <Pagination page={filters.page} total={Math.max(1, Math.ceil(page.count / PAGE_SIZE))} hasNext={page.next !== null} hasPrevious={page.previous !== null} onChange={(next) => update({ page: next })} />
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
  onClear,
}: {
  filters: ReturnType<typeof readJobFilters>
  governorates: Governorate[]
  specialties: Specialty[]
  onChange: (patch: Record<string, string | number | undefined>) => void
  onClear: () => void
}) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const [draft, setDraft] = useState(filters.q ?? '')
  const [applied, setApplied] = useState(filters.q ?? '')
  if (applied !== (filters.q ?? '')) {
    setApplied(filters.q ?? '')
    setDraft(filters.q ?? '')
  }
  const cities = useAsyncData<City[]>((signal) => (filters.governorate ? reference.listCities(filters.governorate, signal) : Promise.resolve([])), [filters.governorate])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    onChange({ q: draft.trim() })
  }

  return (
    <form onSubmit={submit} aria-label={t('providers.filters')}>
      <div className={styles.searchRow}>
        <SearchField label={t('common.search')} placeholder={t('jobsPage.searchPlaceholder')} value={draft} onChange={(e) => setDraft(e.target.value)} />
        <Button type="submit" leading={<Icon name="search" size={18} />}>
          {t('common.search')}
        </Button>
      </div>
      <div className={styles.filters}>
        <Select label={t('jobsPage.filters.profession')} value={filters.profession ?? ''} onChange={(e) => onChange({ profession: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {PROFESSIONS.map((p) => (
            <option key={p} value={p}>
              {t(`professions.${p}`)}
            </option>
          ))}
        </Select>
        <Select label={t('jobsPage.filters.specialty')} value={filters.specialty ?? ''} onChange={(e) => onChange({ specialty: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {specialties.map((s) => (
            <option key={s.id} value={s.slug}>
              {name(s)}
            </option>
          ))}
        </Select>
        <Select label={t('jobsPage.filters.governorate')} value={filters.governorate ?? ''} onChange={(e) => onChange({ governorate: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {governorates.map((g) => (
            <option key={g.id} value={g.id}>
              {name(g)}
            </option>
          ))}
        </Select>
        <Select label={t('jobsPage.filters.city')} adornment={cities.loading && filters.governorate ? <Spinner size="sm" /> : null} value={filters.city ?? ''} disabled={!filters.governorate || cities.loading} onChange={(e) => onChange({ city: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {(cities.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {name(c)}
            </option>
          ))}
        </Select>
        <Select label={t('jobsPage.filters.employment_type')} value={filters.employment_type ?? ''} onChange={(e) => onChange({ employment_type: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {EMPLOYMENT_TYPES.map((v) => (
            <option key={v} value={v}>
              {t(`employmentTypes.${v}`)}
            </option>
          ))}
        </Select>
        <Select label={t('jobsPage.filters.work_mode')} value={filters.work_mode ?? ''} onChange={(e) => onChange({ work_mode: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {WORK_MODES.map((v) => (
            <option key={v} value={v}>
              {t(`workModes.${v}`)}
            </option>
          ))}
        </Select>
        <Select label={t('jobsPage.filters.shift_type')} value={filters.shift_type ?? ''} onChange={(e) => onChange({ shift_type: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {SHIFT_TYPES.map((v) => (
            <option key={v} value={v}>
              {t(`shiftTypes.${v}`)}
            </option>
          ))}
        </Select>
        <Select label={t('jobsPage.filters.degree')} value={filters.degree ?? ''} onChange={(e) => onChange({ degree: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {DEGREES.map((v) => (
            <option key={v} value={v}>
              {t(`degrees.${v}`)}
            </option>
          ))}
        </Select>
        <Select label={t('jobsPage.filters.max_experience')} value={filters.max_experience === undefined ? '' : String(filters.max_experience)} onChange={(e) => onChange({ max_experience: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {[0, 1, 2, 3, 5, 10].map((n) => (
            <option key={n} value={n}>
              {t('jobsPage.maxExperience', { count: n })}
            </option>
          ))}
        </Select>
        <Checkbox label={t('jobsPage.filters.salary_available')} checked={filters.salary_available === 'true'} onChange={(e) => onChange({ salary_available: e.target.checked ? 'true' : '' })} />
        <Button type="button" variant="ghost" onClick={onClear}>
          {t('common.clear')}
        </Button>
      </div>
    </form>
  )
}
