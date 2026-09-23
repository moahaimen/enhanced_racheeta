import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError, AVAILABILITIES, DEGREES, EMPLOYMENT_TYPES, jobs as jobsApi, PROFESSIONS, reference } from '../../api'
import type { Availability, City, Degree, EmploymentType, Governorate, Profession, SeekerProfile, SeekerProfileWrite, Specialty } from '../../api'
import { Alert, ApiActionButton, AsyncPage, Badge, Checkbox, CheckboxGroup, Container, FormActions, FormSection, Icon, PageHeader, PageStack, SectionCard, Select, Spinner, Textarea, TextField, useFormErrors } from '../../design-system'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { ClientValidationError } from '../validation'
import styles from './SeekerProfilePage.module.css'

type Loaded = [SeekerProfile | null, Governorate[], Specialty[]]

/** /jobs/profile — the structured résumé (no files). */
export function SeekerProfilePage() {
  const { t } = useTranslation()
  const load = async (signal: AbortSignal): Promise<Loaded> => {
    const profile = await jobsApi.getMySeekerProfile(signal).catch((e: unknown) => {
      if (e instanceof ApiError && e.status === 404) return null
      throw e
    })
    const [governorates, specialties] = await Promise.all([reference.listGovernorates(undefined, signal), reference.listSpecialties(signal)])
    return [profile, governorates, specialties]
  }
  return (
    <Container width="xl">
      <AsyncPage load={load}>
        {([profile, governorates, specialties], reload) =>
          profile ? (
            <>
              <PageHeader eyebrow={<><Icon name="user" size={16} />{t('nav.jobs')}</>} title={t('seekerProfile.title')} description={t('seekerProfile.intro')} />
              <PageStack>
                <SectionCard title={t('seekerProfile.sectionEdit')} headingLevel={2}>
                  <ProfileForm profile={profile} governorates={governorates} specialties={specialties} onSaved={reload} />
                </SectionCard>
                <ExperienceSection profile={profile} governorates={governorates} reload={reload} />
                <EducationSection profile={profile} reload={reload} />
                <SkillsSection profile={profile} reload={reload} />
                <LanguagesSection profile={profile} reload={reload} />
                <CredentialsSection profile={profile} reload={reload} />
              </PageStack>
            </>
          ) : (
            <Container width="md" style={{ paddingInline: 0 }}>
              <PageHeader eyebrow={<><Icon name="user" size={16} />{t('nav.jobs')}</>} title={t('seekerProfile.onboardingTitle')} description={t('seekerProfile.onboardingIntro')} />
              <div className="card-block">
                <ProfileForm profile={null} governorates={governorates} specialties={specialties} onSaved={reload} />
              </div>
            </Container>
          )
        }
      </AsyncPage>
    </Container>
  )
}

const FIELDS = ['professional_title', 'profession', 'general_specialty', 'detailed_specialty', 'degree', 'institution_name', 'graduation_year', 'years_of_experience', 'professional_summary', 'governorate', 'city', 'desired_governorate', 'employment_preferences', 'availability', 'salary_expectation_min', 'discoverable_by_employers'] as const

function ProfileForm({ profile, governorates, specialties, onSaved }: { profile: SeekerProfile | null; governorates: Governorate[]; specialties: Specialty[]; onSaved: () => void }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const [f, setF] = useState({
    professional_title: profile?.professional_title ?? '',
    profession: (profile?.profession ?? 'NURSE') as Profession,
    general_specialty: profile?.general_specialty?.id ?? '',
    detailed_specialty: profile?.detailed_specialty ?? '',
    degree: (profile?.degree ?? 'BACHELOR') as Degree,
    institution_name: profile?.institution_name ?? '',
    graduation_year: profile?.graduation_year ? String(profile.graduation_year) : '',
    years_of_experience: String(profile?.years_of_experience ?? 0),
    professional_summary: profile?.professional_summary ?? '',
    governorate: profile?.governorate.id ?? '',
    city: profile?.city?.id ?? '',
    desired_governorate: profile?.desired_governorate?.id ?? '',
    employment_preferences: (profile?.employment_preferences ?? ['FULL_TIME']) as EmploymentType[],
    availability: (profile?.availability ?? 'WITHIN_MONTH') as Availability,
    salary_expectation_min: profile?.salary_expectation_min ?? '',
    discoverable_by_employers: profile?.discoverable_by_employers ?? false,
  })
  const [saved, setSaved] = useState(false)
  const errors = useFormErrors(FIELDS)
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }))
  const cities = useAsyncData<City[]>((signal) => (f.governorate ? reference.listCities(f.governorate, signal) : Promise.resolve([])), [f.governorate])

  const submit = async () => {
    setSaved(false)
    const next: Partial<Record<(typeof FIELDS)[number], string>> = {}
    if (!f.professional_title.trim()) next.professional_title = t('validation.required')
    if (!f.governorate) next.governorate = t('validation.required')
    if (f.graduation_year && !/^\d{4}$/.test(f.graduation_year)) next.graduation_year = t('validation.number')
    if (!/^\d{1,2}$/.test(f.years_of_experience)) next.years_of_experience = t('validation.number')
    errors.setFieldErrors(next)
    errors.setFormError(null)
    if (Object.keys(next).length > 0) throw new ClientValidationError()
    const payload: SeekerProfileWrite = {
      professional_title: f.professional_title.trim(),
      profession: f.profession,
      general_specialty: f.general_specialty || null,
      detailed_specialty: f.detailed_specialty.trim(),
      degree: f.degree,
      institution_name: f.institution_name.trim(),
      graduation_year: f.graduation_year ? Number(f.graduation_year) : null,
      years_of_experience: Number(f.years_of_experience),
      professional_summary: f.professional_summary,
      governorate: f.governorate,
      city: f.city || null,
      desired_governorate: f.desired_governorate || null,
      employment_preferences: f.employment_preferences,
      availability: f.availability,
      salary_expectation_min: f.salary_expectation_min.trim() || null,
      discoverable_by_employers: f.discoverable_by_employers,
    }
    return profile ? jobsApi.updateMySeekerProfile(payload) : jobsApi.createMySeekerProfile(payload)
  }

  return (
    <form noValidate onSubmit={(e) => e.preventDefault()}>
      {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
      {saved ? <Alert kind="success">{t('seekerProfile.saved')}</Alert> : null}
      <FormSection title={t('seekerProfile.sectionBasics')}>
        <TextField label={t('seekerProfile.professionalTitle')} name="professional_title" value={f.professional_title} onChange={(e) => set('professional_title', e.target.value)} error={errors.fieldErrors.professional_title} required />
        <div className="grid-2">
          <Select label={t('seekerProfile.profession')} value={f.profession} onChange={(e) => set('profession', e.target.value as Profession)} error={errors.fieldErrors.profession}>
            {PROFESSIONS.map((p) => (
              <option key={p} value={p}>
                {t(`professions.${p}`)}
              </option>
            ))}
          </Select>
          <Select label={t('seekerProfile.specialty')} optional value={f.general_specialty} onChange={(e) => set('general_specialty', e.target.value)} error={errors.fieldErrors.general_specialty}>
            <option value="">—</option>
            {specialties.map((s) => (
              <option key={s.id} value={s.id}>
                {name(s)}
              </option>
            ))}
          </Select>
        </div>
        <TextField label={t('seekerProfile.detailedSpecialty')} optional name="detailed_specialty" value={f.detailed_specialty} onChange={(e) => set('detailed_specialty', e.target.value)} error={errors.fieldErrors.detailed_specialty} />
        <div className="grid-2">
          <Select label={t('seekerProfile.degree')} value={f.degree} onChange={(e) => set('degree', e.target.value as Degree)} error={errors.fieldErrors.degree}>
            {DEGREES.map((d) => (
              <option key={d} value={d}>
                {t(`degrees.${d}`)}
              </option>
            ))}
          </Select>
          <TextField label={t('seekerProfile.institution')} optional name="institution_name" value={f.institution_name} onChange={(e) => set('institution_name', e.target.value)} error={errors.fieldErrors.institution_name} />
        </div>
        <div className="grid-2">
          <TextField label={t('seekerProfile.graduationYear')} optional name="graduation_year" dir="ltr" inputMode="numeric" value={f.graduation_year} onChange={(e) => set('graduation_year', e.target.value)} error={errors.fieldErrors.graduation_year} />
          <TextField label={t('seekerProfile.years')} name="years_of_experience" dir="ltr" inputMode="numeric" value={f.years_of_experience} onChange={(e) => set('years_of_experience', e.target.value)} error={errors.fieldErrors.years_of_experience} required />
        </div>
        <Textarea label={t('seekerProfile.summary')} hint={t('seekerProfile.summaryHint')} name="professional_summary" value={f.professional_summary} onChange={(e) => set('professional_summary', e.target.value)} error={errors.fieldErrors.professional_summary} />
      </FormSection>
      <FormSection title={t('seekerProfile.sectionLocation')}>
        <div className="grid-2">
          <Select label={t('seekerProfile.governorate')} value={f.governorate} error={errors.fieldErrors.governorate} onChange={(e) => { set('governorate', e.target.value); set('city', '') }} required>
            <option value="">—</option>
            {governorates.map((g) => (
              <option key={g.id} value={g.id}>
                {name(g)}
              </option>
            ))}
          </Select>
          <Select label={t('seekerProfile.city')} optional adornment={cities.loading && f.governorate ? <Spinner size="sm" /> : null} value={f.city} disabled={!f.governorate || cities.loading} onChange={(e) => set('city', e.target.value)} error={errors.fieldErrors.city}>
            <option value="">—</option>
            {(cities.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {name(c)}
              </option>
            ))}
          </Select>
        </div>
        <div className="grid-2">
          <Select label={t('seekerProfile.desiredGovernorate')} optional value={f.desired_governorate} onChange={(e) => set('desired_governorate', e.target.value)}>
            <option value="">—</option>
            {governorates.map((g) => (
              <option key={g.id} value={g.id}>
                {name(g)}
              </option>
            ))}
          </Select>
          <Select label={t('seekerProfile.availability')} value={f.availability} onChange={(e) => set('availability', e.target.value as Availability)}>
            {AVAILABILITIES.map((a) => (
              <option key={a} value={a}>
                {t(`availabilities.${a}`)}
              </option>
            ))}
          </Select>
        </div>
        <CheckboxGroup legend={t('seekerProfile.employmentPreferences')} error={errors.fieldErrors.employment_preferences}>
          {EMPLOYMENT_TYPES.map((et) => (
            <Checkbox key={et} label={t(`employmentTypes.${et}`)} checked={f.employment_preferences.includes(et)} onChange={(e) => set('employment_preferences', e.target.checked ? [...f.employment_preferences, et] : f.employment_preferences.filter((x) => x !== et))} />
          ))}
        </CheckboxGroup>
        <TextField label={t('seekerProfile.salaryExpectation')} optional name="salary_expectation_min" dir="ltr" inputMode="decimal" value={f.salary_expectation_min} onChange={(e) => set('salary_expectation_min', e.target.value)} error={errors.fieldErrors.salary_expectation_min} />
      </FormSection>
      <FormSection title={t('seekerProfile.sectionPrivacy')} description={t('seekerProfile.discoverableHint')}>
        <Checkbox label={t('seekerProfile.discoverable')} checked={f.discoverable_by_employers} onChange={(e) => set('discoverable_by_employers', e.target.checked)} />
      </FormSection>
      <FormActions>
        <ApiActionButton type="submit" size="lg" action={submit} onSuccess={() => { setSaved(true); onSaved() }} onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }} pendingLabel={profile ? t('common.saving') : t('seekerProfile.creating')}>
          {profile ? t('common.save') : t('seekerProfile.create')}
        </ApiActionButton>
      </FormActions>
    </form>
  )
}

function RowList({ children }: { children: ReactNode }) {
  return <ul className={styles.list}>{children}</ul>
}

function DeleteButton({ action, reload, onError }: { action: () => Promise<void>; reload: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  return (
    <ApiActionButton variant="ghost" size="sm" action={action} onSuccess={reload} onError={onError} pendingLabel={t('common.deleting')} leading={<Icon name="trash" size={14} />}>
      {t('seekerProfile.delete')}
    </ApiActionButton>
  )
}

function ExperienceSection({ profile, governorates, reload }: { profile: SeekerProfile; governorates: Governorate[]; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const [f, setF] = useState({ title: '', organization_name: '', governorate: '', start_date: '', end_date: '', is_current: false, description: '' })
  const [error, setError] = useState<string | null>(null)
  const errors = useFormErrors(['title', 'organization_name', 'start_date', 'end_date', 'description'] as const)
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }))
  return (
    <SectionCard id="experiences" title={t('seekerProfile.experiences')} headingLevel={2}>
      {error ? <Alert kind="error">{error}</Alert> : null}
      {profile.experiences.length === 0 ? <p className="text-muted">{t('seekerProfile.noItems')}</p> : null}
      <RowList>
        {profile.experiences.map((x) => (
          <li key={x.id} className={styles.row} data-testid="experience-row">
            <div className={styles.rowText}>
              <div className={styles.rowTitle}>{x.title}</div>
              <div className="text-caption">
                {x.organization_name} · {new Date(x.start_date).toLocaleDateString(i18n.language)} – {x.is_current ? t('seekerProfile.current') : x.end_date ? new Date(x.end_date).toLocaleDateString(i18n.language) : ''}
              </div>
            </div>
            <DeleteButton action={() => jobsApi.deleteExperience(x.id)} reload={reload} onError={(e) => setError(toErrorMessage(e))} />
          </li>
        ))}
      </RowList>
      <form noValidate onSubmit={(e) => e.preventDefault()} className={styles.addForm}>
        <h4 className="text-label">{t('seekerProfile.addExperience')}</h4>
        {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
        <div className="grid-2">
          <TextField label={t('seekerProfile.jobTitle')} value={f.title} onChange={(e) => set('title', e.target.value)} error={errors.fieldErrors.title} required />
          <TextField label={t('seekerProfile.organization')} value={f.organization_name} onChange={(e) => set('organization_name', e.target.value)} error={errors.fieldErrors.organization_name} required />
        </div>
        <div className="grid-2">
          <TextField label={t('seekerProfile.startDate')} type="date" dir="ltr" value={f.start_date} onChange={(e) => set('start_date', e.target.value)} error={errors.fieldErrors.start_date} required />
          <TextField label={t('seekerProfile.endDate')} optional type="date" dir="ltr" value={f.end_date} disabled={f.is_current} onChange={(e) => set('end_date', e.target.value)} error={errors.fieldErrors.end_date} />
        </div>
        <Checkbox label={t('seekerProfile.current')} checked={f.is_current} onChange={(e) => set('is_current', e.target.checked)} />
        <Select label={t('seekerProfile.governorate')} optional value={f.governorate} onChange={(e) => set('governorate', e.target.value)}>
          <option value="">—</option>
          {governorates.map((g) => (
            <option key={g.id} value={g.id}>
              {name(g)}
            </option>
          ))}
        </Select>
        <Textarea label={t('seekerProfile.description')} optional rows={2} value={f.description} onChange={(e) => set('description', e.target.value)} error={errors.fieldErrors.description} />
        <FormActions>
          <ApiActionButton
            type="submit"
            action={async () => {
              const next: Record<string, string> = {}
              if (!f.title.trim()) next.title = t('validation.required')
              if (!f.organization_name.trim()) next.organization_name = t('validation.required')
              if (!f.start_date) next.start_date = t('validation.required')
              errors.setFieldErrors(next)
              if (Object.keys(next).length) throw new ClientValidationError()
              return jobsApi.addExperience({ title: f.title.trim(), organization_name: f.organization_name.trim(), governorate: f.governorate || null, start_date: f.start_date, end_date: f.is_current ? null : f.end_date || null, is_current: f.is_current, description: f.description })
            }}
            onSuccess={() => { setF({ title: '', organization_name: '', governorate: '', start_date: '', end_date: '', is_current: false, description: '' }); reload() }}
            onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }}
            leading={<Icon name="plus" size={16} />}
          >
            {t('common.add')}
          </ApiActionButton>
        </FormActions>
      </form>
    </SectionCard>
  )
}

function EducationSection({ profile, reload }: { profile: SeekerProfile; reload: () => void }) {
  const { t } = useTranslation()
  const [f, setF] = useState({ degree: 'BACHELOR' as Degree, field_of_study: '', institution_name: '', start_year: '', end_year: '' })
  const [error, setError] = useState<string | null>(null)
  const errors = useFormErrors(['field_of_study', 'institution_name', 'start_year', 'end_year'] as const)
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }))
  return (
    <SectionCard id="education" title={t('seekerProfile.education')} headingLevel={2}>
      {error ? <Alert kind="error">{error}</Alert> : null}
      {profile.education.length === 0 ? <p className="text-muted">{t('seekerProfile.noItems')}</p> : null}
      <RowList>
        {profile.education.map((x) => (
          <li key={x.id} className={styles.row}>
            <div className={styles.rowText}>
              <div className={styles.rowTitle}>{t(`degrees.${x.degree}`)} · {x.field_of_study}</div>
              <div className="text-caption">{x.institution_name}{x.end_year ? ` · ${x.end_year}` : ''}</div>
            </div>
            <DeleteButton action={() => jobsApi.deleteEducation(x.id)} reload={reload} onError={(e) => setError(toErrorMessage(e))} />
          </li>
        ))}
      </RowList>
      <form noValidate onSubmit={(e) => e.preventDefault()} className={styles.addForm}>
        <h4 className="text-label">{t('seekerProfile.addEducation')}</h4>
        {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
        <div className="grid-2">
          <Select label={t('seekerProfile.degree')} value={f.degree} onChange={(e) => set('degree', e.target.value as Degree)}>
            {DEGREES.map((d) => (
              <option key={d} value={d}>
                {t(`degrees.${d}`)}
              </option>
            ))}
          </Select>
          <TextField label={t('seekerProfile.fieldOfStudy')} value={f.field_of_study} onChange={(e) => set('field_of_study', e.target.value)} error={errors.fieldErrors.field_of_study} required />
        </div>
        <TextField label={t('seekerProfile.institution')} value={f.institution_name} onChange={(e) => set('institution_name', e.target.value)} error={errors.fieldErrors.institution_name} required />
        <div className="grid-2">
          <TextField label={t('seekerProfile.startYear')} optional dir="ltr" inputMode="numeric" value={f.start_year} onChange={(e) => set('start_year', e.target.value)} error={errors.fieldErrors.start_year} />
          <TextField label={t('seekerProfile.endYear')} optional dir="ltr" inputMode="numeric" value={f.end_year} onChange={(e) => set('end_year', e.target.value)} error={errors.fieldErrors.end_year} />
        </div>
        <FormActions>
          <ApiActionButton
            type="submit"
            action={async () => {
              const next: Record<string, string> = {}
              if (!f.field_of_study.trim()) next.field_of_study = t('validation.required')
              if (!f.institution_name.trim()) next.institution_name = t('validation.required')
              errors.setFieldErrors(next)
              if (Object.keys(next).length) throw new ClientValidationError()
              return jobsApi.addEducation({ degree: f.degree, field_of_study: f.field_of_study.trim(), institution_name: f.institution_name.trim(), start_year: f.start_year ? Number(f.start_year) : null, end_year: f.end_year ? Number(f.end_year) : null })
            }}
            onSuccess={() => { setF({ degree: 'BACHELOR', field_of_study: '', institution_name: '', start_year: '', end_year: '' }); reload() }}
            onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }}
            leading={<Icon name="plus" size={16} />}
          >
            {t('common.add')}
          </ApiActionButton>
        </FormActions>
      </form>
    </SectionCard>
  )
}

function SkillsSection({ profile, reload }: { profile: SeekerProfile; reload: () => void }) {
  const { t } = useTranslation()
  const [skill, setSkill] = useState('')
  const [error, setError] = useState<string | null>(null)
  const errors = useFormErrors(['name'] as const)
  return (
    <SectionCard id="skills" title={t('seekerProfile.skills')} headingLevel={2}>
      {error ? <Alert kind="error">{error}</Alert> : null}
      {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
      <div className="cluster" style={{ marginBlockEnd: 'var(--space-3)' }}>
        {profile.skills.length === 0 ? <span className="text-muted">{t('seekerProfile.noItems')}</span> : null}
        {profile.skills.map((s) => (
          <span key={s.id} className="cluster" data-testid="skill-chip" style={{ gap: 'var(--space-1)' }}>
            <Badge tone="outline">{s.name}</Badge>
            <ApiActionButton variant="subtle" size="sm" action={() => jobsApi.deleteSkill(s.id)} onSuccess={reload} onError={(e) => setError(toErrorMessage(e))} aria-label={`${t('seekerProfile.delete')}: ${s.name}`}>
              <Icon name="x" size={14} />
            </ApiActionButton>
          </span>
        ))}
      </div>
      <form noValidate onSubmit={(e) => e.preventDefault()} className={styles.inline}>
        <TextField label={t('seekerProfile.skillName')} value={skill} onChange={(e) => setSkill(e.target.value)} error={errors.fieldErrors.name} />
        <span />
        <ApiActionButton
          type="submit"
          action={async () => {
            if (!skill.trim()) {
              errors.setFieldErrors({ name: t('validation.required') })
              throw new ClientValidationError()
            }
            return jobsApi.addSkill(skill.trim())
          }}
          onSuccess={() => { setSkill(''); errors.clear(); reload() }}
          onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }}
          leading={<Icon name="plus" size={16} />}
        >
          {t('seekerProfile.addSkill')}
        </ApiActionButton>
      </form>
    </SectionCard>
  )
}

function LanguagesSection({ profile, reload }: { profile: SeekerProfile; reload: () => void }) {
  const { t } = useTranslation()
  const [language, setLanguage] = useState('')
  const [level, setLevel] = useState<'BASIC' | 'INTERMEDIATE' | 'ADVANCED' | 'NATIVE'>('INTERMEDIATE')
  const [error, setError] = useState<string | null>(null)
  const errors = useFormErrors(['language', 'level'] as const)
  return (
    <SectionCard id="languages" title={t('seekerProfile.languages')} headingLevel={2}>
      {error ? <Alert kind="error">{error}</Alert> : null}
      {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
      <RowList>
        {profile.languages.length === 0 ? <li className="text-muted">{t('seekerProfile.noItems')}</li> : null}
        {profile.languages.map((l) => (
          <li key={l.id} className={styles.row}>
            <div className={styles.rowText}>
              <span className={styles.rowTitle}>{l.language}</span> <Badge tone="outline">{t(`languageLevels.${l.level}`)}</Badge>
            </div>
            <DeleteButton action={() => jobsApi.deleteLanguage(l.id)} reload={reload} onError={(e) => setError(toErrorMessage(e))} />
          </li>
        ))}
      </RowList>
      <form noValidate onSubmit={(e) => e.preventDefault()} className={`${styles.inline} ${styles.addForm}`}>
        <TextField label={t('seekerProfile.language')} value={language} onChange={(e) => setLanguage(e.target.value)} error={errors.fieldErrors.language} />
        <Select label={t('seekerProfile.level')} value={level} onChange={(e) => setLevel(e.target.value as typeof level)}>
          {(['BASIC', 'INTERMEDIATE', 'ADVANCED', 'NATIVE'] as const).map((lv) => (
            <option key={lv} value={lv}>
              {t(`languageLevels.${lv}`)}
            </option>
          ))}
        </Select>
        <ApiActionButton
          type="submit"
          action={async () => {
            if (!language.trim()) {
              errors.setFieldErrors({ language: t('validation.required') })
              throw new ClientValidationError()
            }
            return jobsApi.addLanguage({ language: language.trim(), level })
          }}
          onSuccess={() => { setLanguage(''); errors.clear(); reload() }}
          onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }}
          leading={<Icon name="plus" size={16} />}
        >
          {t('seekerProfile.addLanguage')}
        </ApiActionButton>
      </form>
    </SectionCard>
  )
}

function CredentialsSection({ profile, reload }: { profile: SeekerProfile; reload: () => void }) {
  const { t } = useTranslation()
  const [f, setF] = useState({ kind: 'LICENSE' as 'LICENSE' | 'CERTIFICATION', name: '', issuer: '', year: '' })
  const [error, setError] = useState<string | null>(null)
  const errors = useFormErrors(['name', 'issuer', 'year'] as const)
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }))
  return (
    <SectionCard id="credentials" title={t('seekerProfile.credentials')} headingLevel={2}>
      {error ? <Alert kind="error">{error}</Alert> : null}
      {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
      <RowList>
        {profile.credentials.length === 0 ? <li className="text-muted">{t('seekerProfile.noItems')}</li> : null}
        {profile.credentials.map((c) => (
          <li key={c.id} className={styles.row}>
            <div className={styles.rowText}>
              <div className={styles.rowTitle}>{c.name}</div>
              <div className="text-caption">{t(`seekerProfile.kinds.${c.kind}`)}{c.issuer ? ` · ${c.issuer}` : ''}{c.year ? ` · ${c.year}` : ''}</div>
            </div>
            <DeleteButton action={() => jobsApi.deleteCredential(c.id)} reload={reload} onError={(e) => setError(toErrorMessage(e))} />
          </li>
        ))}
      </RowList>
      <form noValidate onSubmit={(e) => e.preventDefault()} className={styles.addForm}>
        <div className="grid-2">
          <Select label={t('seekerProfile.credentialKind')} value={f.kind} onChange={(e) => set('kind', e.target.value as typeof f.kind)}>
            <option value="LICENSE">{t('seekerProfile.kinds.LICENSE')}</option>
            <option value="CERTIFICATION">{t('seekerProfile.kinds.CERTIFICATION')}</option>
          </Select>
          <TextField label={t('seekerProfile.credentialName')} value={f.name} onChange={(e) => set('name', e.target.value)} error={errors.fieldErrors.name} required />
        </div>
        <div className="grid-2">
          <TextField label={t('seekerProfile.issuer')} optional value={f.issuer} onChange={(e) => set('issuer', e.target.value)} error={errors.fieldErrors.issuer} />
          <TextField label={t('seekerProfile.year')} optional dir="ltr" inputMode="numeric" value={f.year} onChange={(e) => set('year', e.target.value)} error={errors.fieldErrors.year} />
        </div>
        <FormActions>
          <ApiActionButton
            type="submit"
            action={async () => {
              if (!f.name.trim()) {
                errors.setFieldErrors({ name: t('validation.required') })
                throw new ClientValidationError()
              }
              return jobsApi.addCredential({ kind: f.kind, name: f.name.trim(), issuer: f.issuer.trim(), year: f.year ? Number(f.year) : null })
            }}
            onSuccess={() => { setF({ kind: 'LICENSE', name: '', issuer: '', year: '' }); errors.clear(); reload() }}
            onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }}
            leading={<Icon name="plus" size={16} />}
          >
            {t('seekerProfile.addCredential')}
          </ApiActionButton>
        </FormActions>
      </form>
    </SectionCard>
  )
}
