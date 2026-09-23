import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'

import { AVAILABILITIES, DEGREES, EMPLOYMENT_TYPES, jobs as jobsApi, PROFESSIONS, reference } from '../../api'
import type { Governorate, Specialty, TalentParams } from '../../api'
import { AsyncPage, Button, Container, EmptyState, Icon, PageHeader, PageStack, Pagination, SearchField, Select, Spinner, TalentCard } from '../../design-system'
import { useLocalizedName } from '../../i18n/localized'
import styles from '../jobs/JobsPage.module.css'

const KEYS = ['q', 'profession', 'specialty', 'degree', 'min_experience', 'governorate', 'city', 'skill', 'language', 'availability', 'employment_type'] as const
const PAGE_SIZE = 12

function read(params: URLSearchParams): TalentParams & { page: number } {
  const out: Record<string, string> = {}
  for (const k of KEYS) {
    const v = params.get(k)
    if (v) out[k] = v
  }
  return { ...(out as TalentParams), page: Math.max(1, Number(params.get('page') ?? '1') || 1) }
}

/** /employer/talent — entitlement-gated talent discovery. One search per filter set per day is charged. */
export function TalentSearchPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const filters = read(params)
  const update = (patch: Record<string, string | number | undefined>) => {
    const next: Record<string, string | number | undefined> = { ...filters, ...patch }
    if (patch.page === undefined) next.page = 1
    const out = new URLSearchParams()
    for (const [k, v] of Object.entries(next)) {
      if (v === undefined || v === '' || (k === 'page' && Number(v) === 1)) continue
      out.set(k, String(v))
    }
    setParams(out)
  }
  return (
    <Container width="xl">
      <PageHeader
        eyebrow={
          <Link to="/employer" className="cluster">
            <Icon name="chevronBack" size={14} flipInRtl /> {t('nav.employer')}
          </Link>
        }
        title={t('talent.title')}
        description={t('talent.intro')}
      />
      <PageStack>
        <section className="card-block">
          <AsyncPage load={(signal) => Promise.all([reference.listGovernorates(undefined, signal), reference.listSpecialties(signal)])} skeleton={<Spinner size="sm" />}>
            {([governorates, specialties]) => <TalentFilters filters={filters} governorates={governorates} specialties={specialties} onChange={update} onClear={() => setParams(new URLSearchParams())} />}
          </AsyncPage>
          <p className="text-caption" style={{ marginBlockStart: 'var(--space-3)' }}>
            {t('talent.searchNote')}
          </p>
        </section>
        <AsyncPage load={(signal) => jobsApi.searchTalent({ ...filters, page_size: PAGE_SIZE }, signal)} deps={[...KEYS.map((k) => filters[k] ?? ''), filters.page]}>
          {(page) => (
            <>
              <p className={styles.summary} data-testid="talent-count">
                <span className={styles.count}>{t('talent.results', { count: page.count })}</span>
              </p>
              {page.results.length === 0 ? (
                <div className="card-block">
                  <EmptyState icon="users" title={t('talent.empty')} testId="talent-empty" />
                </div>
              ) : (
                <ul className={styles.grid} aria-label={t('talent.title')}>
                  {page.results.map((c) => (
                    <li key={c.id}>
                      <TalentCard candidate={c} />
                    </li>
                  ))}
                </ul>
              )}
              <Pagination page={filters.page} total={Math.max(1, Math.ceil(page.count / PAGE_SIZE))} hasNext={page.next !== null} hasPrevious={page.previous !== null} onChange={(p) => update({ page: p })} />
            </>
          )}
        </AsyncPage>
      </PageStack>
    </Container>
  )
}

function TalentFilters({ filters, governorates, specialties, onChange, onClear }: { filters: ReturnType<typeof read>; governorates: Governorate[]; specialties: Specialty[]; onChange: (patch: Record<string, string | number | undefined>) => void; onClear: () => void }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const [draft, setDraft] = useState({ q: filters.q ?? '', skill: filters.skill ?? '', language: filters.language ?? '' })
  const [applied, setApplied] = useState(`${filters.q ?? ''}|${filters.skill ?? ''}|${filters.language ?? ''}`)
  const current = `${filters.q ?? ''}|${filters.skill ?? ''}|${filters.language ?? ''}`
  if (applied !== current) {
    setApplied(current)
    setDraft({ q: filters.q ?? '', skill: filters.skill ?? '', language: filters.language ?? '' })
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    onChange({ q: draft.q.trim(), skill: draft.skill.trim(), language: draft.language.trim() })
  }
  return (
    <form onSubmit={submit} aria-label={t('providers.filters')}>
      <div className={styles.searchRow}>
        <SearchField label={t('common.search')} placeholder={t('talent.filters.q')} value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} />
        <Button type="submit" leading={<Icon name="search" size={18} />}>
          {t('common.search')}
        </Button>
      </div>
      <div className={styles.filters}>
        <Select label={t('talent.filters.profession')} value={filters.profession ?? ''} onChange={(e) => onChange({ profession: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {PROFESSIONS.map((p) => (
            <option key={p} value={p}>
              {t(`professions.${p}`)}
            </option>
          ))}
        </Select>
        <Select label={t('talent.filters.specialty')} value={filters.specialty ?? ''} onChange={(e) => onChange({ specialty: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {specialties.map((s) => (
            <option key={s.id} value={s.slug}>
              {name(s)}
            </option>
          ))}
        </Select>
        <Select label={t('talent.filters.degree')} value={filters.degree ?? ''} onChange={(e) => onChange({ degree: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {DEGREES.map((d) => (
            <option key={d} value={d}>
              {t(`degrees.${d}`)}
            </option>
          ))}
        </Select>
        <Select label={t('talent.filters.min_experience')} value={filters.min_experience === undefined ? '' : String(filters.min_experience)} onChange={(e) => onChange({ min_experience: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {[1, 2, 3, 5, 10].map((n) => (
            <option key={n} value={n}>
              {t('talent.experienceYears', { count: n })}+
            </option>
          ))}
        </Select>
        <Select label={t('talent.filters.governorate')} value={filters.governorate ?? ''} onChange={(e) => onChange({ governorate: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {governorates.map((g) => (
            <option key={g.id} value={g.id}>
              {name(g)}
            </option>
          ))}
        </Select>
        <Select label={t('talent.filters.availability')} value={filters.availability ?? ''} onChange={(e) => onChange({ availability: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {AVAILABILITIES.map((a) => (
            <option key={a} value={a}>
              {t(`availabilities.${a}`)}
            </option>
          ))}
        </Select>
        <Select label={t('talent.filters.employment_type')} value={filters.employment_type ?? ''} onChange={(e) => onChange({ employment_type: e.target.value })}>
          <option value="">{t('common.all')}</option>
          {EMPLOYMENT_TYPES.map((v) => (
            <option key={v} value={v}>
              {t(`employmentTypes.${v}`)}
            </option>
          ))}
        </Select>
        <SearchField label={t('talent.filters.skill')} placeholder={t('talent.filters.skill')} value={draft.skill} onChange={(e) => setDraft({ ...draft, skill: e.target.value })} />
        <SearchField label={t('talent.filters.language')} placeholder={t('talent.filters.language')} value={draft.language} onChange={(e) => setDraft({ ...draft, language: e.target.value })} />
        <Button type="button" variant="ghost" onClick={onClear}>
          {t('common.clear')}
        </Button>
      </div>
    </form>
  )
}
