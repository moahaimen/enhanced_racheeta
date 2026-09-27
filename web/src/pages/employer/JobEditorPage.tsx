import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'

import { ApiError, DEGREES, EMPLOYMENT_TYPES, jobs as jobsApi, PROFESSIONS, reference, SHIFT_TYPES, WORK_MODES } from '../../api'
import type { BillingSummary, City, Degree, EmployerOwner, EmploymentType, Governorate, JobEmployer, JobWrite, Profession, ShiftType, Specialty, WorkMode } from '../../api'
import { Alert, ApiActionButton, AsyncPage, Checkbox, Container, FormActions, FormSection, Icon, JobStatusBadge, LinkButton, PageHeader, PageStack, SectionCard, Select, Spinner, Textarea, TextField, useFormErrors } from '../../design-system'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { ClientValidationError } from '../validation'
import styles from './EmployerWorkspacePage.module.css'
import { entitled } from './entitlements'

type Loaded = [JobEmployer | null, EmployerOwner, Governorate[], Specialty[], BillingSummary | null]

/** /employer/jobs/new and /employer/jobs/:id — draft editing and lifecycle actions. */
export function JobEditorPage() {
  const { t } = useTranslation()
  const { id } = useParams()
  const load = async (signal: AbortSignal): Promise<Loaded> => {
    const employer = await jobsApi.getMyEmployer(signal)
    // The plan's capabilities gate the premium actions; a failed summary fails closed (null → no capability).
    const [governorates, specialties, billing] = await Promise.all([
      reference.listGovernorates(undefined, signal),
      reference.listSpecialties(signal),
      jobsApi.getEmployerBilling(signal).catch(() => null),
    ])
    if (!id) return [null, employer, governorates, specialties, billing]
    try {
      return [await jobsApi.getEmployerJob(id, signal), employer, governorates, specialties, billing]
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) throw new ApiError(404, 'not_found', t('jobEditor.notFound'))
      throw e
    }
  }
  return (
    <Container width="xl">
      <AsyncPage load={load} deps={[id]}>
        {([job, employer, governorates, specialties, billing], reload) => <Editor job={job} employer={employer} governorates={governorates} specialties={specialties} billing={billing} reload={reload} />}
      </AsyncPage>
    </Container>
  )
}

const FIELDS = ['title', 'profession', 'general_specialty', 'detailed_specialty', 'description', 'responsibilities', 'requirements', 'minimum_degree', 'minimum_experience_years', 'governorate', 'city', 'workplace_text', 'employment_type', 'work_mode', 'shift_type', 'salary_min', 'salary_max', 'salary_currency', 'salary_visible', 'number_of_openings', 'application_deadline', 'hiring_employer', 'hiring_organization_name'] as const

function Editor({ job, employer, governorates, specialties, billing, reload }: { job: JobEmployer | null; employer: EmployerOwner; governorates: Governorate[]; specialties: Specialty[]; billing: BillingSummary | null; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const name = useLocalizedName()
  const canWrite = employer.my_role === 'OWNER' || employer.my_role === 'RECRUITER'
  // Premium actions follow the plan (backend: jobs.featured to feature, jobs.post to submit). Removing a
  // premium state (unfeature) needs no entitlement, so an already-featured job keeps that action.
  const canFeature = entitled(billing, 'jobs.featured')
  const canPost = entitled(billing, 'jobs.post')
  // The applicant list is a READ gate (any member) on a recruiting organisation with jobs.application_review.
  const canReviewApplicants = employer.verification_status === 'VERIFIED' && employer.recruitment_status === 'ACTIVE' && entitled(billing, 'jobs.application_review')
  const editable = canWrite && (job === null || job.status === 'DRAFT' || job.status === 'REJECTED')
  // Agency-only values kept by a job whose organisation is no longer an agency.
  // Only worth saying while the job can actually be saved (the save clears them).
  const retainedHiring = job !== null && editable && (job.hiring_employer !== null || job.hiring_organization_name !== '')
  const [f, setF] = useState({
    title: job?.title ?? '',
    profession: (job?.profession ?? 'NURSE') as Profession,
    general_specialty: job?.general_specialty?.id ?? '',
    detailed_specialty: job?.detailed_specialty ?? '',
    description: job?.description ?? '',
    responsibilities: job?.responsibilities ?? '',
    requirements: job?.requirements ?? '',
    minimum_degree: (job?.minimum_degree ?? '') as Degree | '',
    minimum_experience_years: String(job?.minimum_experience_years ?? 0),
    governorate: job?.governorate.id ?? employer.governorate.id,
    city: job?.city?.id ?? '',
    workplace_text: job?.workplace_text ?? '',
    employment_type: (job?.employment_type ?? 'FULL_TIME') as EmploymentType,
    work_mode: (job?.work_mode ?? 'ON_SITE') as WorkMode,
    shift_type: (job?.shift_type ?? '') as ShiftType | '',
    salary_min: job?.salary_min ?? '',
    salary_max: job?.salary_max ?? '',
    salary_currency: job?.salary_currency ?? 'IQD',
    salary_visible: job?.salary_visible ?? false,
    number_of_openings: String(job?.number_of_openings ?? 1),
    application_deadline: job?.application_deadline ?? '',
    hiring_employer: job?.hiring_employer?.id ?? '',
    hiring_organization_name: job?.hiring_organization_name ?? '',
  })
  const [saved, setSaved] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const errors = useFormErrors(FIELDS)
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }))
  const cities = useAsyncData<City[]>((signal) => (f.governorate ? reference.listCities(f.governorate, signal) : Promise.resolve([])), [f.governorate])

  const save = async () => {
    setSaved(false)
    const next: Partial<Record<(typeof FIELDS)[number], string>> = {}
    if (!f.title.trim()) next.title = t('validation.required')
    if (!f.description.trim()) next.description = t('validation.required')
    if (!f.governorate) next.governorate = t('validation.required')
    if (!/^\d{1,2}$/.test(f.minimum_experience_years)) next.minimum_experience_years = t('validation.number')
    if (!/^\d{1,3}$/.test(f.number_of_openings) || Number(f.number_of_openings) < 1) next.number_of_openings = t('validation.number')
    if (f.salary_min && f.salary_max && Number(f.salary_min) > Number(f.salary_max)) next.salary_max = t('jobEditorErrors.salaryRange')
    errors.setFieldErrors(next)
    errors.setFormError(null)
    if (Object.keys(next).length) throw new ClientValidationError()
    const payload: JobWrite = {
      title: f.title.trim(),
      profession: f.profession,
      general_specialty: f.general_specialty || null,
      detailed_specialty: f.detailed_specialty.trim(),
      description: f.description,
      responsibilities: f.responsibilities,
      requirements: f.requirements,
      minimum_degree: f.minimum_degree,
      minimum_experience_years: Number(f.minimum_experience_years),
      governorate: f.governorate,
      city: f.city || null,
      workplace_text: f.workplace_text.trim(),
      employment_type: f.employment_type,
      work_mode: f.work_mode,
      shift_type: f.shift_type,
      salary_min: f.salary_min.trim() || null,
      salary_max: f.salary_max.trim() || null,
      salary_currency: f.salary_currency,
      salary_visible: f.salary_visible,
      number_of_openings: Number(f.number_of_openings),
      application_deadline: f.application_deadline || null,
    }
    if (employer.is_recruitment_agency) {
      payload.hiring_employer = f.hiring_employer || null
      payload.hiring_organization_name = f.hiring_organization_name.trim()
    } else if (job) {
      // The organisation is not (or is no longer) an agency. The backend
      // validates the RESULTING job, so a draft created while it *was* one
      // keeps values the form cannot show — and every later edit or submit is
      // refused. Sending the clearing values explicitly repairs the draft;
      // nothing else is touched, and `retainedHiring` tells the user first.
      payload.hiring_employer = null
      payload.hiring_organization_name = ''
    }
    // A brand-new job of a non-agency never sends agency-only values at all.
    return job ? jobsApi.updateJob(job.id, payload) : jobsApi.createJob(payload)
  }

  return (
    <>
      <PageHeader
        eyebrow={
          <Link to="/employer" className="cluster">
            <Icon name="chevronBack" size={14} flipInRtl /> {t('nav.employer')}
          </Link>
        }
        title={job ? job.title : t('jobEditor.newTitle')}
        description={t('jobEditor.intro')}
        actions={job ? <JobStatusBadge status={job.status} /> : undefined}
      />
      <PageStack>
        {job ? (
          <SectionCard title={t('jobEditor.status')} headingLevel={2} actions={job.status === 'PUBLISHED' ? <LinkButton to={`/jobs/${job.id}`} variant="ghost" size="sm" leading={<Icon name="externalLink" size={16} />}>{t('jobEditor.viewPublic')}</LinkButton> : undefined}>
            {actionError ? <Alert kind="error">{actionError}</Alert> : null}
            {job.moderation_note ? <Alert kind={job.status === 'REJECTED' || job.status === 'SUSPENDED' ? 'warning' : 'info'} title={t('jobEditor.moderationNote')}>{job.moderation_note}</Alert> : null}
            {job.moderation_flags.length > 0 ? (
              <Alert kind="error" title={t('jobEditor.flags')}>
                <ul>
                  {job.moderation_flags.map((fl, i) => (
                    <li key={i}>
                      {t(`jobEditor.${fl.field}`, { defaultValue: fl.field })}: {fl.category} — “{fl.excerpt}”
                    </li>
                  ))}
                </ul>
              </Alert>
            ) : null}
            <div className={styles.rowActions} style={{ marginBlockStart: 'var(--space-3)' }}>
              {canWrite && canPost && (job.status === 'DRAFT' || job.status === 'REJECTED') ? (
                <ApiActionButton action={() => jobsApi.jobAction(job.id, 'submit')} onSuccess={reload} onError={(e) => setActionError(toErrorMessage(e))} pendingLabel={t('common.submitting')} leading={<Icon name="check" size={18} />}>
                  {t('jobEditor.submit')}
                </ApiActionButton>
              ) : null}
              {canWrite && (job.status === 'PUBLISHED' || job.status === 'PENDING_ADMIN_REVIEW' || job.status === 'EXPIRED') ? (
                <ApiActionButton variant="ghost" action={() => jobsApi.jobAction(job.id, 'close')} onSuccess={reload} onError={(e) => setActionError(toErrorMessage(e))} pendingLabel={t('common.closing')}>
                  {t('jobEditor.close')}
                </ApiActionButton>
              ) : null}
              {canWrite && job.status === 'PUBLISHED' && (job.is_featured || canFeature) ? (
                <ApiActionButton variant={job.is_featured ? 'ghost' : 'secondary'} action={() => jobsApi.featureJob(job.id, !job.is_featured)} onSuccess={reload} onError={(e) => setActionError(toErrorMessage(e))} leading={<Icon name="sparkle" size={18} />}>
                  {job.is_featured ? t('jobEditor.unfeature') : t('jobEditor.feature')}
                </ApiActionButton>
              ) : null}
              {canWrite && ['DRAFT', 'CLOSED', 'EXPIRED', 'REJECTED'].includes(job.status) ? (
                <ApiActionButton variant="ghost" action={() => jobsApi.jobAction(job.id, 'archive')} onSuccess={() => navigate('/employer')} onError={(e) => setActionError(toErrorMessage(e))}>
                  {t('jobEditor.archive')}
                </ApiActionButton>
              ) : null}
              {canReviewApplicants ? (
                <LinkButton to={`/employer/jobs/${job.id}/applications`} variant="ghost">
                  {t('jobEditor.applicants')} ({job.applications_count})
                </LinkButton>
              ) : null}
            </div>
            {job.transitions.length > 0 ? (
              <ol className="text-caption" style={{ marginBlockStart: 'var(--space-3)', paddingInlineStart: 'var(--space-5)' }}>
                {job.transitions.map((tr, i) => (
                  <li key={i}>
                    {t(`jobStatus.${tr.to_status}`)} · {new Date(tr.created_at).toLocaleString(i18n.language)}
                    {tr.reason ? ` · ${tr.reason}` : ''}
                  </li>
                ))}
              </ol>
            ) : null}
          </SectionCard>
        ) : null}

        <SectionCard title={job ? t('jobEditor.editTitle') : t('jobEditor.newTitle')} headingLevel={2}>
          {!canWrite ? <Alert kind="info">{t('jobEditor.viewerReadOnly')}</Alert> : !editable ? <Alert kind="info">{t('jobEditor.locked')}</Alert> : null}
          <form noValidate onSubmit={(e) => e.preventDefault()}>
            {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
            {saved ? <Alert kind="success">{t('employer.saved')}</Alert> : null}
            <fieldset disabled={!editable} style={{ border: 0, padding: 0, margin: 0 }}>
              <FormSection title={t('jobEditor.sectionRole')}>
                <TextField label={t('jobEditor.title')} name="title" value={f.title} onChange={(e) => set('title', e.target.value)} error={errors.fieldErrors.title} required />
                <div className="grid-2">
                  <Select label={t('jobEditor.profession')} value={f.profession} onChange={(e) => set('profession', e.target.value as Profession)} error={errors.fieldErrors.profession}>
                    {PROFESSIONS.map((p) => (
                      <option key={p} value={p}>
                        {t(`professions.${p}`)}
                      </option>
                    ))}
                  </Select>
                  <Select label={t('jobEditor.specialty')} optional value={f.general_specialty} onChange={(e) => set('general_specialty', e.target.value)} error={errors.fieldErrors.general_specialty}>
                    <option value="">—</option>
                    {specialties.map((s) => (
                      <option key={s.id} value={s.id}>
                        {name(s)}
                      </option>
                    ))}
                  </Select>
                </div>
                <TextField label={t('jobEditor.detailedSpecialty')} optional value={f.detailed_specialty} onChange={(e) => set('detailed_specialty', e.target.value)} error={errors.fieldErrors.detailed_specialty} />
                <Textarea label={t('jobEditor.description')} name="description" rows={5} value={f.description} onChange={(e) => set('description', e.target.value)} error={errors.fieldErrors.description} required />
                <Textarea label={t('jobEditor.responsibilities')} optional rows={4} value={f.responsibilities} onChange={(e) => set('responsibilities', e.target.value)} error={errors.fieldErrors.responsibilities} />
              </FormSection>
              <FormSection title={t('jobEditor.sectionRequirements')}>
                <Textarea label={t('jobEditor.requirements')} optional rows={4} value={f.requirements} onChange={(e) => set('requirements', e.target.value)} error={errors.fieldErrors.requirements} />
                <div className="grid-2">
                  <Select label={t('jobEditor.minDegree')} optional value={f.minimum_degree} onChange={(e) => set('minimum_degree', e.target.value as Degree | '')}>
                    <option value="">{t('common.unspecified')}</option>
                    {DEGREES.map((d) => (
                      <option key={d} value={d}>
                        {t(`degrees.${d}`)}
                      </option>
                    ))}
                  </Select>
                  <TextField label={t('jobEditor.minExperience')} dir="ltr" inputMode="numeric" value={f.minimum_experience_years} onChange={(e) => set('minimum_experience_years', e.target.value)} error={errors.fieldErrors.minimum_experience_years} />
                </div>
              </FormSection>
              <FormSection title={t('jobEditor.sectionLocation')}>
                <div className="grid-2">
                  <Select label={t('jobEditor.governorate')} value={f.governorate} error={errors.fieldErrors.governorate} onChange={(e) => { set('governorate', e.target.value); set('city', '') }} required>
                    <option value="">—</option>
                    {governorates.map((g) => (
                      <option key={g.id} value={g.id}>
                        {name(g)}
                      </option>
                    ))}
                  </Select>
                  <Select label={t('jobEditor.city')} optional adornment={cities.loading && f.governorate ? <Spinner size="sm" /> : null} value={f.city} disabled={!f.governorate || cities.loading} onChange={(e) => set('city', e.target.value)} error={errors.fieldErrors.city}>
                    <option value="">—</option>
                    {(cities.data ?? []).map((c) => (
                      <option key={c.id} value={c.id}>
                        {name(c)}
                      </option>
                    ))}
                  </Select>
                </div>
                <TextField label={t('jobEditor.workplace')} optional value={f.workplace_text} onChange={(e) => set('workplace_text', e.target.value)} error={errors.fieldErrors.workplace_text} />
                <div className="grid-2">
                  <Select label={t('jobEditor.employmentType')} value={f.employment_type} onChange={(e) => set('employment_type', e.target.value as EmploymentType)}>
                    {EMPLOYMENT_TYPES.map((v) => (
                      <option key={v} value={v}>
                        {t(`employmentTypes.${v}`)}
                      </option>
                    ))}
                  </Select>
                  <Select label={t('jobEditor.workMode')} value={f.work_mode} onChange={(e) => set('work_mode', e.target.value as WorkMode)}>
                    {WORK_MODES.map((v) => (
                      <option key={v} value={v}>
                        {t(`workModes.${v}`)}
                      </option>
                    ))}
                  </Select>
                </div>
                <Select label={t('jobEditor.shift')} optional value={f.shift_type} onChange={(e) => set('shift_type', e.target.value as ShiftType | '')}>
                  <option value="">{t('common.unspecified')}</option>
                  {SHIFT_TYPES.map((v) => (
                    <option key={v} value={v}>
                      {t(`shiftTypes.${v}`)}
                    </option>
                  ))}
                </Select>
              </FormSection>
              <FormSection title={t('jobEditor.sectionSalary')}>
                <div className="grid-2">
                  <TextField label={t('jobEditor.salaryMin')} optional dir="ltr" inputMode="decimal" value={f.salary_min} onChange={(e) => set('salary_min', e.target.value)} error={errors.fieldErrors.salary_min} />
                  <TextField label={t('jobEditor.salaryMax')} optional dir="ltr" inputMode="decimal" value={f.salary_max} onChange={(e) => set('salary_max', e.target.value)} error={errors.fieldErrors.salary_max} />
                </div>
                <div className="grid-2">
                  <Select label={t('jobEditor.currency')} value={f.salary_currency} onChange={(e) => set('salary_currency', e.target.value)}>
                    <option value="IQD">IQD</option>
                    <option value="USD">USD</option>
                  </Select>
                  <TextField label={t('jobEditor.openings')} dir="ltr" inputMode="numeric" value={f.number_of_openings} onChange={(e) => set('number_of_openings', e.target.value)} error={errors.fieldErrors.number_of_openings} />
                </div>
                <Checkbox label={t('jobEditor.salaryVisible')} checked={f.salary_visible} onChange={(e) => set('salary_visible', e.target.checked)} />
                <TextField label={t('jobEditor.deadline')} optional type="date" dir="ltr" value={f.application_deadline} onChange={(e) => set('application_deadline', e.target.value)} error={errors.fieldErrors.application_deadline} />
              </FormSection>
              {!employer.is_recruitment_agency && retainedHiring ? (
                <FormSection title={t('jobEditor.sectionAgency')}>
                  <Alert kind="warning" testId="retained-hiring-notice">{t('jobEditor.retainedHiring')}</Alert>
                </FormSection>
              ) : null}
              {employer.is_recruitment_agency ? (
                <FormSection title={t('jobEditor.sectionAgency')}>
                  <TextField label={t('jobEditor.hiringEmployer')} optional dir="ltr" value={f.hiring_employer} onChange={(e) => set('hiring_employer', e.target.value)} error={errors.fieldErrors.hiring_employer} />
                  <TextField label={t('jobEditor.hiringName')} optional value={f.hiring_organization_name} onChange={(e) => set('hiring_organization_name', e.target.value)} error={errors.fieldErrors.hiring_organization_name} />
                </FormSection>
              ) : null}
            </fieldset>
            {editable ? (
              <FormActions>
                <ApiActionButton type="submit" size="lg" action={save} onSuccess={(saved) => { setSaved(true); if (!job) navigate(`/employer/jobs/${saved.id}`, { replace: true }); else reload() }} onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }} pendingLabel={t('common.saving')}>
                  {job ? t('jobEditor.save') : t('jobEditor.create')}
                </ApiActionButton>
              </FormActions>
            ) : null}
          </form>
        </SectionCard>
      </PageStack>
    </>
  )
}
