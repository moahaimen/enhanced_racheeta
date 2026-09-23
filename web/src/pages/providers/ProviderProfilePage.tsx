import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { ApiError, providers as providersApi, reference } from '../../api'
import type { Governorate, Membership, ProviderOwner, ServiceOffering, Specialty } from '../../api'
import { ApiActionButton, AsyncPage, Spinner } from '../../components'
import { FormAlert, TextField, useFormErrors } from '../../components/forms'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { ClientValidationError } from '../validation'
import { ProviderTypeBadge, VerificationBadge } from './ProviderBadges'
import { ProviderForm } from './ProviderForm'

type Loaded = [ProviderOwner | null, Governorate[], Specialty[]]

/**
 * /provider/profile — provider onboarding and self-management. Guarded by
 * RequireAuth + RequireRole('PROVIDER') in the route table.
 */
export function ProviderProfilePage() {
  const load = async (signal: AbortSignal): Promise<Loaded> => {
    const profile = await providersApi.getMyProvider(signal).catch((error: unknown) => {
      if (error instanceof ApiError && error.status === 404) return null
      throw error
    })
    const [governorates, specialties] = await Promise.all([
      reference.listGovernorates(undefined, signal),
      reference.listSpecialties(signal),
    ])
    return [profile, governorates, specialties]
  }

  return (
    <AsyncPage load={load}>
      {([profile, governorates, specialties], reload) =>
        profile ? (
          <Dashboard profile={profile} governorates={governorates} specialties={specialties} reload={reload} />
        ) : (
          <Onboarding governorates={governorates} specialties={specialties} onCreated={reload} />
        )
      }
    </AsyncPage>
  )
}

function Onboarding({
  governorates,
  specialties,
  onCreated,
}: {
  governorates: Governorate[]
  specialties: Specialty[]
  onCreated: () => void
}) {
  const { t } = useTranslation()
  return (
    <section className="card">
      <h2>{t('providerProfile.onboardingTitle')}</h2>
      <p className="muted">{t('providerProfile.onboardingIntro')}</p>
      <ProviderForm
        profile={null}
        governorates={governorates}
        specialties={specialties}
        submit={(payload) => providersApi.createMyProvider(payload)}
        onSaved={onCreated}
        submitLabel={t('providerProfile.create')}
        pendingLabel={t('providerProfile.creating')}
      />
    </section>
  )
}

function Dashboard({
  profile: initial,
  governorates,
  specialties,
  reload,
}: {
  profile: ProviderOwner
  governorates: Governorate[]
  specialties: Specialty[]
  reload: () => void
}) {
  const { t } = useTranslation()
  const [profile, setProfile] = useState(initial)
  const [verificationError, setVerificationError] = useState<string | null>(null)
  const canRequest = profile.verification_status === 'UNVERIFIED' || profile.verification_status === 'REJECTED'

  return (
    <>
      <section className="card">
        <h2>{t('providerProfile.title')}</h2>
        <dl className="status">
          <dt>{t('providers.type')}</dt>
          <dd>
            <ProviderTypeBadge type={profile.provider_type} />
          </dd>
          <dt>{t('providerProfile.status')}</dt>
          <dd>
            <VerificationBadge status={profile.verification_status} />
          </dd>
          {profile.verification_note ? (
            <>
              <dt>{t('providerProfile.statusNote')}</dt>
              <dd>{profile.verification_note}</dd>
            </>
          ) : null}
        </dl>
        <p className="muted">{t('providerProfile.verificationHint')}</p>
        {verificationError ? <FormAlert kind="error">{verificationError}</FormAlert> : null}
        <div className="actions">
          {canRequest ? (
            <ApiActionButton
              action={() => providersApi.requestVerification()}
              onSuccess={(updated) => {
                setVerificationError(null)
                setProfile(updated)
              }}
              onError={(error) => setVerificationError(toErrorMessage(error))}
              pendingLabel={t('providerProfile.requestingVerification')}
            >
              {t('providerProfile.requestVerification')}
            </ApiActionButton>
          ) : null}
          {profile.verification_status === 'VERIFIED' ? (
            <Link className="btn btn--ghost" to={`/providers/${profile.id}`}>
              {t('providers.viewProfile')}
            </Link>
          ) : null}
          <button type="button" className="btn btn--ghost" onClick={reload}>
            {t('common.retry')}
          </button>
        </div>
      </section>

      <section className="card">
        <h3>{t('providerProfile.details')}</h3>
        <ProviderForm
          key={profile.updated_at}
          profile={profile}
          governorates={governorates}
          specialties={specialties}
          submit={(payload) => providersApi.updateMyProvider(payload)}
          onSaved={setProfile}
          submitLabel={t('common.save')}
          pendingLabel={t('common.saving')}
        />
      </section>

      <ServicesSection specialties={specialties} />
      <MembershipsSection profile={profile} />
    </>
  )
}

// ---- services -------------------------------------------------------------

const SERVICE_FIELDS = ['title', 'description', 'price', 'currency', 'duration_minutes', 'specialty'] as const

function ServicesSection({ specialties }: { specialties: Specialty[] }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const services = useAsyncData<ServiceOffering[]>((signal) => providersApi.listMyServices(signal), [])
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [price, setPrice] = useState('')
  const [currency, setCurrency] = useState('IQD')
  const [duration, setDuration] = useState('')
  const [specialty, setSpecialty] = useState('')
  const [rowError, setRowError] = useState<string | null>(null)
  const errors = useFormErrors(SERVICE_FIELDS)

  const add = async () => {
    const next: Partial<Record<(typeof SERVICE_FIELDS)[number], string>> = {}
    if (!title.trim()) next.title = t('validation.required')
    if (price.trim() === '' || Number.isNaN(Number(price)) || Number(price) < 0) next.price = t('validation.number')
    if (duration.trim() && (!Number.isInteger(Number(duration)) || Number(duration) <= 0)) {
      next.duration_minutes = t('validation.number')
    }
    errors.setFieldErrors(next)
    errors.setFormError(null)
    if (Object.keys(next).length > 0) throw new ClientValidationError()
    return providersApi.createMyService({
      title: title.trim(),
      description: description.trim(),
      price: price.trim(),
      currency,
      duration_minutes: duration.trim() ? Number(duration) : null,
      specialty: specialty || null,
    })
  }

  return (
    <section className="card">
      <h3>{t('providerProfile.services')}</h3>
      {services.loading ? (
        <div className="async-state" data-testid="services-loading">
          <Spinner />
        </div>
      ) : services.error ? (
        <div className="async-state async-state--error" role="alert">
          <p>{toErrorMessage(services.error)}</p>
          <button type="button" className="btn" onClick={services.reload}>
            {t('common.retry')}
          </button>
        </div>
      ) : (services.data ?? []).length === 0 ? (
        <p className="muted" data-testid="services-empty">
          {t('providerProfile.noServices')}
        </p>
      ) : (
        <table className="table">
          <tbody>
            {(services.data ?? []).map((s) => (
              <tr key={s.id} data-testid="service-row">
                <td>
                  <strong>{s.title}</strong>
                  {s.specialty ? (
                    <div className="muted">{name(specialties.find((sp) => sp.id === s.specialty))}</div>
                  ) : null}
                </td>
                <td dir="ltr">
                  {Number(s.price).toLocaleString(i18n.language)} {s.currency}
                </td>
                <td>{s.duration_minutes ? t('providerDetail.duration', { minutes: s.duration_minutes }) : ''}</td>
                <td>
                  <ApiActionButton
                    className="btn--ghost btn--sm"
                    action={() => providersApi.updateMyService(s.id, { is_active: !s.is_active })}
                    onSuccess={() => {
                      setRowError(null)
                      services.reload()
                    }}
                    onError={(error) => setRowError(toErrorMessage(error))}
                    aria-label={`${t('providerProfile.serviceActive')}: ${s.title}`}
                  >
                    {s.is_active ? t('common.yes') : t('common.no')}
                  </ApiActionButton>
                </td>
                <td>
                  <ApiActionButton
                    className="btn--ghost btn--sm"
                    action={() => providersApi.deleteMyService(s.id)}
                    onSuccess={() => {
                      setRowError(null)
                      services.reload()
                    }}
                    onError={(error) => setRowError(toErrorMessage(error))}
                    pendingLabel={t('common.deleting')}
                    aria-label={`${t('common.delete')}: ${s.title}`}
                  >
                    {t('common.delete')}
                  </ApiActionButton>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {rowError ? <FormAlert kind="error">{rowError}</FormAlert> : null}

      <h4>{t('providerProfile.addService')}</h4>
      <form noValidate onSubmit={(e) => e.preventDefault()}>
        {errors.formError ? <FormAlert kind="error">{errors.formError}</FormAlert> : null}
        <TextField
          label={t('providerProfile.serviceTitle')}
          name="title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          error={errors.fieldErrors.title}
          required
        />
        <TextField
          label={t('providerProfile.serviceDescription')}
          name="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <div className="grid-2">
          <TextField
            label={t('providerProfile.servicePrice')}
            name="price"
            dir="ltr"
            inputMode="decimal"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            error={errors.fieldErrors.price}
            required
          />
          <div className="field">
            <label className="field__label" htmlFor="svc-currency">
              {t('providerProfile.serviceCurrency')}
            </label>
            <div className="field__control">
              <select
                id="svc-currency"
                className="field__input"
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
              >
                <option value="IQD">IQD</option>
                <option value="USD">USD</option>
              </select>
            </div>
          </div>
        </div>
        <div className="grid-2">
          <TextField
            label={t('providerProfile.serviceDuration')}
            name="duration_minutes"
            dir="ltr"
            inputMode="numeric"
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            error={errors.fieldErrors.duration_minutes}
          />
          <div className="field">
            <label className="field__label" htmlFor="svc-specialty">
              {t('providers.specialty')}
            </label>
            <div className="field__control">
              <select
                id="svc-specialty"
                className="field__input"
                value={specialty}
                onChange={(e) => setSpecialty(e.target.value)}
              >
                <option value="">—</option>
                {specialties.map((s) => (
                  <option key={s.id} value={s.id}>
                    {name(s)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
        <div className="form__actions">
          <ApiActionButton
            type="submit"
            action={add}
            onSuccess={() => {
              setTitle('')
              setDescription('')
              setPrice('')
              setDuration('')
              setSpecialty('')
              services.reload()
            }}
            onError={(error) => {
              if (!(error instanceof ClientValidationError)) errors.applyApiError(error)
            }}
          >
            {t('common.add')}
          </ApiActionButton>
        </div>
      </form>
    </section>
  )
}

// ---- memberships ----------------------------------------------------------

function MembershipsSection({ profile }: { profile: ProviderOwner }) {
  const { t } = useTranslation()
  const memberships = useAsyncData<Membership[]>((signal) => providersApi.listMyMemberships(signal), [])
  const [counterpart, setCounterpart] = useState('')
  const [roleTitle, setRoleTitle] = useState('')
  const [rowError, setRowError] = useState<string | null>(null)
  const errors = useFormErrors(['counterpart', 'role_title'] as const)
  const isPractitioner = profile.kind === 'PRACTITIONER'

  const request = async () => {
    errors.clear()
    if (!counterpart.trim()) {
      errors.setFieldErrors({ counterpart: t('validation.required') })
      throw new ClientValidationError()
    }
    return providersApi.createMembership(counterpart.trim(), roleTitle.trim())
  }

  const act = (m: Membership, action: 'accept' | 'reject' | 'end') => () => providersApi.membershipAction(m.id, action)

  return (
    <section className="card">
      <h3>{t('providerProfile.memberships')}</h3>
      <p className="muted">
        {isPractitioner ? t('providerProfile.membershipsIntroPractitioner') : t('providerProfile.membershipsIntroFacility')}
      </p>
      {memberships.loading ? (
        <div className="async-state" data-testid="memberships-loading">
          <Spinner />
        </div>
      ) : memberships.error ? (
        <div className="async-state async-state--error" role="alert">
          <p>{toErrorMessage(memberships.error)}</p>
          <button type="button" className="btn" onClick={memberships.reload}>
            {t('common.retry')}
          </button>
        </div>
      ) : (memberships.data ?? []).length === 0 ? (
        <p className="muted" data-testid="memberships-empty">
          {t('providerProfile.noMemberships')}
        </p>
      ) : (
        <table className="table">
          <tbody>
            {(memberships.data ?? []).map((m) => {
              const other = m.my_side === 'PRACTITIONER' ? m.facility : m.practitioner
              return (
                <tr key={m.id} data-testid="membership-row">
                  <td>
                    <Link to={`/providers/${other.id}`}>{other.display_name}</Link>{' '}
                    <ProviderTypeBadge type={other.provider_type} />
                    {m.role_title ? <div className="muted">{m.role_title}</div> : null}
                  </td>
                  <td>
                    <span className="badge">{t(`membershipStatus.${m.status}`)}</span>
                  </td>
                  <td className="actions">
                    {m.status === 'PENDING' && m.can_accept ? (
                      <ApiActionButton
                        className="btn--sm"
                        action={act(m, 'accept')}
                        onSuccess={() => {
                          setRowError(null)
                          memberships.reload()
                        }}
                        onError={(error) => setRowError(toErrorMessage(error))}
                      >
                        {t('providerProfile.accept')}
                      </ApiActionButton>
                    ) : null}
                    {m.status === 'PENDING' ? (
                      <ApiActionButton
                        className="btn--ghost btn--sm"
                        action={act(m, 'reject')}
                        onSuccess={() => {
                          setRowError(null)
                          memberships.reload()
                        }}
                        onError={(error) => setRowError(toErrorMessage(error))}
                      >
                        {m.can_accept ? t('providerProfile.reject') : t('providerProfile.withdraw')}
                      </ApiActionButton>
                    ) : null}
                    {m.status === 'ACTIVE' ? (
                      <ApiActionButton
                        className="btn--ghost btn--sm"
                        action={act(m, 'end')}
                        onSuccess={() => {
                          setRowError(null)
                          memberships.reload()
                        }}
                        onError={(error) => setRowError(toErrorMessage(error))}
                      >
                        {t('providerProfile.end')}
                      </ApiActionButton>
                    ) : null}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
      {rowError ? <FormAlert kind="error">{rowError}</FormAlert> : null}

      <form noValidate onSubmit={(e) => e.preventDefault()}>
        {errors.formError ? <FormAlert kind="error">{errors.formError}</FormAlert> : null}
        <div className="grid-2">
          <TextField
            label={t('providerProfile.counterpartId')}
            name="counterpart"
            dir="ltr"
            value={counterpart}
            onChange={(e) => setCounterpart(e.target.value)}
            error={errors.fieldErrors.counterpart}
            required
          />
          <TextField
            label={t('providerProfile.roleTitle')}
            name="role_title"
            value={roleTitle}
            onChange={(e) => setRoleTitle(e.target.value)}
            error={errors.fieldErrors.role_title}
          />
        </div>
        <div className="form__actions">
          <ApiActionButton
            type="submit"
            action={request}
            onSuccess={() => {
              setCounterpart('')
              setRoleTitle('')
              memberships.reload()
            }}
            onError={(error) => {
              if (!(error instanceof ClientValidationError)) errors.applyApiError(error)
            }}
          >
            {t('providerProfile.requestMembership')}
          </ApiActionButton>
        </div>
      </form>
    </section>
  )
}
