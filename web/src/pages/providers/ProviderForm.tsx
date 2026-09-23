import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PROVIDER_TYPES, reference } from '../../api'
import type { City, Governorate, ProviderOwner, ProviderType, ProviderWrite, Specialty } from '../../api'
import {
  Alert,
  ApiActionButton,
  Checkbox,
  CheckboxGroup,
  FormActions,
  FormSection,
  Icon,
  Select,
  Spinner,
  Textarea,
  TextField,
  useFormErrors,
} from '../../design-system'
import { useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { ClientValidationError, isEmail, isPhone } from '../validation'

const FIELDS = [
  'provider_type',
  'display_name',
  'about',
  'phone',
  'public_email',
  'website',
  'governorate',
  'city',
  'address',
  'latitude',
  'longitude',
  'image_url',
  'specialty_ids',
  'is_visible',
] as const

interface FormState {
  provider_type: ProviderType
  display_name: string
  about: string
  phone: string
  public_email: string
  website: string
  governorate: string
  city: string
  address: string
  latitude: string
  longitude: string
  image_url: string
  specialty_ids: string[]
  is_visible: boolean
}

function fromProfile(profile: ProviderOwner | null): FormState {
  return {
    provider_type: profile?.provider_type ?? 'DOCTOR',
    display_name: profile?.display_name ?? '',
    about: profile?.about ?? '',
    phone: profile?.phone ?? '',
    public_email: profile?.public_email ?? '',
    website: profile?.website ?? '',
    governorate: profile?.governorate.id ?? '',
    city: profile?.city?.id ?? '',
    address: profile?.address ?? '',
    latitude: profile?.latitude ?? '',
    longitude: profile?.longitude ?? '',
    image_url: profile?.image_url ?? '',
    specialty_ids: profile?.specialties.map((s) => s.id) ?? [],
    is_visible: profile?.is_visible ?? true,
  }
}

export interface ProviderFormProps {
  profile: ProviderOwner | null
  governorates: Governorate[]
  specialties: Specialty[]
  submit: (payload: ProviderWrite) => Promise<ProviderOwner>
  onSaved: (profile: ProviderOwner) => void
  submitLabel: string
  pendingLabel: string
}

/** Shared by onboarding (create) and editing (update). Grouped into form sections. */
export function ProviderForm({ profile, governorates, specialties, submit, onSaved, submitLabel, pendingLabel }: ProviderFormProps) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const [form, setForm] = useState<FormState>(() => fromProfile(profile))
  const [saved, setSaved] = useState(false)
  const errors = useFormErrors(FIELDS)
  const typeLocked = profile !== null && !profile.can_change_type

  const cities = useAsyncData<City[]>(
    (signal) => (form.governorate ? reference.listCities(form.governorate, signal) : Promise.resolve([])),
    [form.governorate],
  )

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((prev) => ({ ...prev, [key]: value }))

  const validate = (): boolean => {
    const next: Partial<Record<(typeof FIELDS)[number], string>> = {}
    if (!form.display_name.trim()) next.display_name = t('validation.required')
    if (!form.governorate) next.governorate = t('validation.required')
    if (form.phone.trim() && !isPhone(form.phone)) next.phone = t('validation.phone')
    if (form.public_email.trim() && !isEmail(form.public_email)) next.public_email = t('validation.email')
    if (form.website.trim() && !/^https?:\/\//.test(form.website.trim())) next.website = t('validation.url')
    if (form.image_url.trim() && !form.image_url.trim().startsWith('https://')) next.image_url = t('validation.url')
    const lat = form.latitude.trim()
    const lng = form.longitude.trim()
    if ((lat === '') !== (lng === '')) next.latitude = t('validation.required')
    if (lat && (Number.isNaN(Number(lat)) || Math.abs(Number(lat)) > 90)) next.latitude = t('validation.number')
    if (lng && (Number.isNaN(Number(lng)) || Math.abs(Number(lng)) > 180)) next.longitude = t('validation.number')
    errors.setFieldErrors(next)
    errors.setFormError(null)
    return Object.keys(next).length === 0
  }

  const action = async () => {
    setSaved(false)
    if (!validate()) throw new ClientValidationError()
    const payload: ProviderWrite = {
      display_name: form.display_name.trim(),
      about: form.about,
      phone: form.phone.replace(/[\s-]/g, ''),
      public_email: form.public_email.trim(),
      website: form.website.trim(),
      governorate: form.governorate,
      city: form.city || null,
      address: form.address.trim(),
      latitude: form.latitude.trim() || null,
      longitude: form.longitude.trim() || null,
      image_url: form.image_url.trim(),
      specialty_ids: form.specialty_ids,
    }
    if (!typeLocked) payload.provider_type = form.provider_type
    if (profile) payload.is_visible = form.is_visible
    return submit(payload)
  }

  return (
    <form noValidate onSubmit={(e) => e.preventDefault()}>
      {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
      {saved ? <Alert kind="success">{t('providerProfile.saved')}</Alert> : null}

      <FormSection title={t('providerProfile.sectionIdentity')}>
        <Select
          label={t('providers.type')}
          value={form.provider_type}
          disabled={typeLocked}
          hint={typeLocked ? t('providerProfile.typeLocked') : undefined}
          error={errors.fieldErrors.provider_type}
          onChange={(e) => set('provider_type', e.target.value as ProviderType)}
        >
          {PROVIDER_TYPES.map((code) => (
            <option key={code} value={code}>
              {t(`providerTypes.${code}`)}
            </option>
          ))}
        </Select>
        <TextField
          label={t('providerProfile.displayName')}
          name="display_name"
          value={form.display_name}
          onChange={(e) => set('display_name', e.target.value)}
          error={errors.fieldErrors.display_name}
          required
        />
        <Textarea label={t('providerProfile.about')} name="about" value={form.about} onChange={(e) => set('about', e.target.value)} />
        <TextField
          label={t('providerProfile.imageUrl')}
          optional
          type="url"
          name="image_url"
          dir="ltr"
          value={form.image_url}
          onChange={(e) => set('image_url', e.target.value)}
          error={errors.fieldErrors.image_url}
        />
      </FormSection>

      <FormSection title={t('providerProfile.sectionContact')}>
        <div className="grid-2">
          <TextField
            label={t('fields.phone')}
            type="tel"
            name="phone"
            dir="ltr"
            leading={<Icon name="phone" size={18} />}
            value={form.phone}
            onChange={(e) => set('phone', e.target.value)}
            error={errors.fieldErrors.phone}
          />
          <TextField
            label={t('providerProfile.publicEmail')}
            type="email"
            name="public_email"
            dir="ltr"
            leading={<Icon name="mail" size={18} />}
            value={form.public_email}
            onChange={(e) => set('public_email', e.target.value)}
            error={errors.fieldErrors.public_email}
          />
        </div>
        <TextField
          label={t('providerProfile.website')}
          type="url"
          name="website"
          dir="ltr"
          leading={<Icon name="link" size={18} />}
          value={form.website}
          onChange={(e) => set('website', e.target.value)}
          error={errors.fieldErrors.website}
        />
      </FormSection>

      <FormSection title={t('providerProfile.sectionLocation')}>
        <div className="grid-2">
          <Select
            label={t('providers.governorate')}
            value={form.governorate}
            error={errors.fieldErrors.governorate}
            onChange={(e) => {
              set('governorate', e.target.value)
              set('city', '')
            }}
            required
          >
            <option value="">—</option>
            {governorates.map((g) => (
              <option key={g.id} value={g.id}>
                {name(g)}
              </option>
            ))}
          </Select>
          <Select
            label={t('providers.city')}
            adornment={cities.loading && form.governorate ? <Spinner size="sm" /> : null}
            value={form.city}
            disabled={!form.governorate || cities.loading}
            error={errors.fieldErrors.city}
            onChange={(e) => set('city', e.target.value)}
          >
            <option value="">—</option>
            {(cities.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {name(c)}
              </option>
            ))}
          </Select>
        </div>
        <TextField label={t('providerProfile.address')} name="address" value={form.address} onChange={(e) => set('address', e.target.value)} error={errors.fieldErrors.address} />
        <div className="grid-2">
          <TextField
            label={t('providerProfile.latitude')}
            name="latitude"
            dir="ltr"
            inputMode="decimal"
            value={form.latitude}
            onChange={(e) => set('latitude', e.target.value)}
            error={errors.fieldErrors.latitude}
          />
          <TextField
            label={t('providerProfile.longitude')}
            name="longitude"
            dir="ltr"
            inputMode="decimal"
            value={form.longitude}
            onChange={(e) => set('longitude', e.target.value)}
            error={errors.fieldErrors.longitude}
          />
        </div>
      </FormSection>

      <FormSection title={t('providerProfile.specialties')}>
        <CheckboxGroup legend={t('providerProfile.specialties')} error={errors.fieldErrors.specialty_ids}>
          {specialties.map((s) => (
            <Checkbox
              key={s.id}
              label={name(s)}
              checked={form.specialty_ids.includes(s.id)}
              onChange={(e) =>
                set('specialty_ids', e.target.checked ? [...form.specialty_ids, s.id] : form.specialty_ids.filter((id) => id !== s.id))
              }
            />
          ))}
        </CheckboxGroup>
      </FormSection>

      {profile ? (
        <FormSection title={t('providerProfile.sectionVisibility')}>
          <Checkbox label={t('providerProfile.visible')} checked={form.is_visible} onChange={(e) => set('is_visible', e.target.checked)} />
        </FormSection>
      ) : null}

      <FormActions>
        <ApiActionButton
          type="submit"
          size="lg"
          action={action}
          onSuccess={(result) => {
            setSaved(true)
            onSaved(result)
          }}
          onError={(error) => {
            if (!(error instanceof ClientValidationError)) errors.applyApiError(error)
          }}
          pendingLabel={pendingLabel}
        >
          {submitLabel}
        </ApiActionButton>
      </FormActions>
    </form>
  )
}
