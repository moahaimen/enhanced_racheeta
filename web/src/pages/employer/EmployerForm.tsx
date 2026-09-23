import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { jobs as jobsApi, ORGANIZATION_TYPES, reference } from '../../api'
import type { City, EmployerOwner, EmployerWrite, Governorate, OrganizationType } from '../../api'
import { Alert, ApiActionButton, Checkbox, FormActions, Select, Spinner, Textarea, TextField, useFormErrors } from '../../design-system'
import { useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { ClientValidationError } from '../validation'

const FIELDS = ['name', 'organization_type', 'description', 'governorate', 'city', 'provider_profile', 'is_recruitment_agency', 'is_discoverable'] as const

export function EmployerForm({ employer, governorates, onSaved }: { employer: EmployerOwner | null; governorates: Governorate[]; onSaved: (e: EmployerOwner) => void }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const [f, setF] = useState({
    name: employer?.name ?? '',
    organization_type: (employer?.organization_type ?? 'HOSPITAL') as OrganizationType,
    description: employer?.description ?? '',
    governorate: employer?.governorate.id ?? '',
    city: employer?.city?.id ?? '',
    is_recruitment_agency: employer?.is_recruitment_agency ?? false,
    is_discoverable: employer?.is_discoverable ?? true,
  })
  const [saved, setSaved] = useState(false)
  const errors = useFormErrors(FIELDS)
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }))
  const cities = useAsyncData<City[]>((signal) => (f.governorate ? reference.listCities(f.governorate, signal) : Promise.resolve([])), [f.governorate])

  const submit = async () => {
    setSaved(false)
    const next: Partial<Record<(typeof FIELDS)[number], string>> = {}
    if (!f.name.trim()) next.name = t('validation.required')
    if (!f.governorate) next.governorate = t('validation.required')
    errors.setFieldErrors(next)
    errors.setFormError(null)
    if (Object.keys(next).length) throw new ClientValidationError()
    const payload: EmployerWrite = { name: f.name.trim(), organization_type: f.organization_type, description: f.description, governorate: f.governorate, city: f.city || null, is_recruitment_agency: f.is_recruitment_agency, is_discoverable: f.is_discoverable }
    return employer ? jobsApi.updateMyEmployer(payload) : jobsApi.createMyEmployer(payload)
  }

  return (
    <form noValidate onSubmit={(e) => e.preventDefault()}>
      {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
      {saved ? <Alert kind="success">{t('employer.saved')}</Alert> : null}
      <TextField label={t('employer.orgName')} name="name" value={f.name} onChange={(e) => set('name', e.target.value)} error={errors.fieldErrors.name} required />
      <Select label={t('employer.orgType')} value={f.organization_type} onChange={(e) => set('organization_type', e.target.value as OrganizationType)} error={errors.fieldErrors.organization_type}>
        {ORGANIZATION_TYPES.map((o) => (
          <option key={o} value={o}>
            {t(`organizationTypes.${o}`)}
          </option>
        ))}
      </Select>
      <Textarea label={t('employer.description')} hint={t('employer.descriptionHint')} value={f.description} onChange={(e) => set('description', e.target.value)} error={errors.fieldErrors.description} />
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
      <Checkbox label={t('employer.isAgency')} checked={f.is_recruitment_agency} onChange={(e) => set('is_recruitment_agency', e.target.checked)} />
      <Checkbox label={t('employer.discoverable')} checked={f.is_discoverable} onChange={(e) => set('is_discoverable', e.target.checked)} />
      <FormActions>
        <ApiActionButton type="submit" size="lg" action={submit} onSuccess={(e) => { setSaved(true); onSaved(e) }} onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }} pendingLabel={employer ? t('common.saving') : t('employer.creating')}>
          {employer ? t('common.save') : t('employer.create')}
        </ApiActionButton>
      </FormActions>
    </form>
  )
}
