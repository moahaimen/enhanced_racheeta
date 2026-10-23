import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'

import { reference } from '../../api'
import type { Governorate } from '../../api'
import { useAsyncData } from '../../hooks/useAsync'
import { Icon, type IconName } from '../../design-system'
import { useLocalizedName } from '../../i18n/localized'
import styles from './Home.module.css'

type Target = 'doctors' | 'facilities' | 'jobs' | 'estate'

const TARGETS: { key: Target; icon: IconName; accent: string }[] = [
  { key: 'doctors', icon: 'stethoscope', accent: 'teal' },
  { key: 'facilities', icon: 'hospital', accent: 'blue' },
  { key: 'jobs', icon: 'briefcase', accent: 'indigo' },
  { key: 'estate', icon: 'building', accent: 'coral' },
]

const TAB_LABEL: Record<Target, string> = {
  doctors: 'home.searchTabDoctors',
  facilities: 'home.searchTabFacilities',
  jobs: 'home.searchTabJobs',
  estate: 'home.searchTabEstate',
}
const PLACEHOLDER: Record<Target, string> = {
  doctors: 'home.searchPlaceholderDoctors',
  facilities: 'home.searchPlaceholderFacilities',
  jobs: 'home.searchPlaceholderJobs',
  estate: 'home.searchPlaceholderEstate',
}

/**
 * One premium search surface. There is no universal search endpoint, so the control routes the
 * query to the existing, backend-filtered search of the chosen area (providers, facilities, jobs,
 * real estate) with the parameters each page already understands.
 */
export function HeroSearch() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const name = useLocalizedName()
  const groupId = useId()
  const [target, setTarget] = useState<Target>('doctors')
  const [governorate, setGovernorate] = useState('')
  const [query, setQuery] = useState('')
  const governorates = useAsyncData<Governorate[]>((signal) => reference.listGovernorates(undefined, signal), [])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const params = new URLSearchParams()
    const text = query.trim()
    if (governorate) params.set('governorate', governorate)
    let path = '/providers'
    if (target === 'doctors') params.set('kind', 'PRACTITIONER')
    if (target === 'facilities') params.set('kind', 'FACILITY')
    if (target === 'doctors' || target === 'facilities') {
      if (text) params.set('search', text)
    } else if (target === 'jobs') {
      path = '/jobs'
      if (text) params.set('q', text)
    } else {
      path = '/real-estate'
      if (text) params.set('search', text)
    }
    const qs = params.toString()
    navigate(qs ? `${path}?${qs}` : path)
  }

  return (
    <form className={styles.search} onSubmit={submit} aria-label={t('home.searchTitle')}>
      <fieldset className={styles.searchTabs}>
        <legend className="visually-hidden">{t('home.searchWhat')}</legend>
        {TARGETS.map((item) => (
          <label key={item.key} className={styles.searchTab} data-accent={item.accent} data-active={target === item.key}>
            <input type="radio" name={`${groupId}-target`} value={item.key} checked={target === item.key} onChange={() => setTarget(item.key)} />
            <Icon name={item.icon} size={18} />
            <span>{t(TAB_LABEL[item.key])}</span>
          </label>
        ))}
      </fieldset>
      <div className={styles.searchRow}>
        <label className={styles.searchField}>
          <span className="visually-hidden">{t('common.search')}</span>
          <Icon name="search" size={20} />
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t(PLACEHOLDER[target])} autoComplete="off" />
        </label>
        <label className={styles.searchSelect}>
          <span className="visually-hidden">{t('providers.governorate')}</span>
          <Icon name="mapPin" size={18} />
          <select value={governorate} onChange={(event) => setGovernorate(event.target.value)} disabled={governorates.loading || governorates.data === undefined}>
            <option value="">{t('providers.governorate')}: {t('common.all')}</option>
            {(governorates.data ?? []).map((g) => (
              <option key={g.id} value={g.id}>
                {name(g)}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className={styles.searchButton}>
          <Icon name="search" size={18} />
          {t('home.searchSubmit')}
        </button>
      </div>
    </form>
  )
}
