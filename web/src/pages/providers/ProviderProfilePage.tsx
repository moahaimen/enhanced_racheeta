import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { ApiError, providers as providersApi, reference } from '../../api'
import type { Governorate, Membership, ProviderOwner, ServiceOffering, Specialty } from '../../api'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Avatar,
  Badge,
  Button,
  Container,
  EmptyState,
  ErrorState,
  FormActions,
  Icon,
  LinkButton,
  LoadingState,
  PageHeader,
  PageStack,
  PROVIDER_TYPE_ICON,
  SectionCard,
  Select,
  StatCard,
  Textarea,
  TextField,
  useFormErrors,
} from '../../design-system'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { ClientValidationError } from '../validation'
import { VerificationBadge } from './ProviderBadges'
import { ProviderForm } from './ProviderForm'
import styles from './ProviderProfilePage.module.css'

type Loaded = [ProviderOwner | null, Governorate[], Specialty[]]

/**
 * /provider/profile — provider onboarding and self-management workspace.
 * Guarded by RequireAuth + RequireRole('PROVIDER') in the route table.
 */
export function ProviderProfilePage() {
  const { t } = useTranslation()
  const load = async (signal: AbortSignal): Promise<Loaded> => {
    const profile = await providersApi.getMyProvider(signal).catch((error: unknown) => {
      if (error instanceof ApiError && error.status === 404) return null
      throw error
    })
    const [governorates, specialties] = await Promise.all([reference.listGovernorates(undefined, signal), reference.listSpecialties(signal)])
    return [profile, governorates, specialties]
  }

  return (
    <Container width="xl">
      <AsyncPage load={load} loadingLabel={t('common.loading')}>
        {([profile, governorates, specialties], reload) =>
          profile ? (
            <Workspace profile={profile} governorates={governorates} specialties={specialties} reload={reload} />
          ) : (
            <Onboarding governorates={governorates} specialties={specialties} onCreated={reload} />
          )
        }
      </AsyncPage>
    </Container>
  )
}

function Onboarding({ governorates, specialties, onCreated }: { governorates: Governorate[]; specialties: Specialty[]; onCreated: () => void }) {
  const { t } = useTranslation()
  return (
    <Container width="md" style={{ paddingInline: 0 }}>
      <PageHeader
        eyebrow={
          <>
            <Icon name="briefcase" size={16} />
            {t('nav.providerProfile')}
          </>
        }
        title={t('providerProfile.onboardingTitle')}
        description={t('providerProfile.onboardingIntro')}
      />
      <div className="card-block">
        <ProviderForm
          profile={null}
          governorates={governorates}
          specialties={specialties}
          submit={(payload) => providersApi.createMyProvider(payload)}
          onSaved={onCreated}
          submitLabel={t('providerProfile.create')}
          pendingLabel={t('providerProfile.creating')}
        />
      </div>
    </Container>
  )
}

const SECTIONS = [
  { id: 'overview', icon: 'sparkle', key: 'overview' },
  { id: 'verification', icon: 'shieldCheck', key: 'verification' },
  { id: 'details', icon: 'edit', key: 'details' },
  { id: 'services', icon: 'tag', key: 'services' },
  { id: 'memberships', icon: 'users', key: 'memberships' },
] as const

function Workspace({ profile: initial, governorates, specialties, reload }: { profile: ProviderOwner; governorates: Governorate[]; specialties: Specialty[]; reload: () => void }) {
  const { t } = useTranslation()
  const [profile, setProfile] = useState(initial)
  const services = useAsyncData<ServiceOffering[]>((signal) => providersApi.listMyServices(signal), [])
  const memberships = useAsyncData<Membership[]>((signal) => providersApi.listMyMemberships(signal), [])
  const activeMemberships = (memberships.data ?? []).filter((m) => m.status === 'ACTIVE').length
  const pendingMemberships = (memberships.data ?? []).filter((m) => m.status === 'PENDING').length

  return (
    <>
      <PageHeader
        eyebrow={
          <>
            <Icon name="briefcase" size={16} />
            {t('nav.providerProfile')}
          </>
        }
        title={t('providerProfile.title')}
        description={t('providerProfile.workspaceIntro')}
        actions={
          <>
            {profile.verification_status === 'VERIFIED' ? (
              <LinkButton to={`/providers/${profile.id}`} variant="secondary" leading={<Icon name="externalLink" size={18} />}>
                {t('providers.viewProfile')}
              </LinkButton>
            ) : null}
            <Button variant="ghost" onClick={reload} leading={<Icon name="refresh" size={18} />}>
              {t('common.retry')}
            </Button>
          </>
        }
      />
      <div className={styles.layout}>
        <nav className={styles.sideNav} aria-label={t('providerProfile.sections')}>
          {SECTIONS.map((s) => (
            <a key={s.id} href={`#${s.id}`}>
              <Icon name={s.icon} size={18} />
              {t(`providerProfile.nav.${s.key}`)}
            </a>
          ))}
        </nav>
        <PageStack>
          <SectionCard id="overview" title={t('providerProfile.nav.overview')} headingLevel={2}>
            <div className={styles.statusRow} style={{ marginBlockEnd: 'var(--space-5)' }}>
              <Avatar src={profile.image_url || null} name={profile.display_name} size="lg" fallback={<Icon name={PROVIDER_TYPE_ICON[profile.provider_type]} size={28} />} />
              <div>
                <p style={{ fontWeight: 600, fontSize: 'var(--text-section)' }}>{profile.display_name}</p>
                <div className="cluster" style={{ marginBlockStart: 'var(--space-1)' }}>
                  <Badge tone="brand">{t(`providerTypes.${profile.provider_type}`)}</Badge>
                  <Badge tone="outline">{t(`providerKinds.${profile.kind}`)}</Badge>
                  <VerificationBadge status={profile.verification_status} />
                  {!profile.is_visible ? <Badge tone="warning">{t('providerProfile.hidden')}</Badge> : null}
                </div>
              </div>
            </div>
            <div className={styles.stats}>
              <StatCard label={t('providerProfile.nav.services')} value={services.data ? services.data.length : <Icon name="clock" size={22} />} />
              <StatCard label={t('providerProfile.activeMemberships')} value={memberships.data ? activeMemberships : <Icon name="clock" size={22} />} hint={memberships.data && pendingMemberships > 0 ? t('providerProfile.pendingMemberships', { count: pendingMemberships }) : undefined} />
              <StatCard label={t('providerProfile.specialties')} value={profile.specialties.length} />
            </div>
          </SectionCard>

          <VerificationSection profile={profile} onChange={setProfile} />

          <SectionCard id="details" title={t('providerProfile.nav.details')} description={t('providerProfile.detailsIntro')} headingLevel={2}>
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
          </SectionCard>

          <ServicesSection specialties={specialties} services={services} />
          <MembershipsSection profile={profile} memberships={memberships} />
        </PageStack>
      </div>
    </>
  )
}

function VerificationSection({ profile, onChange }: { profile: ProviderOwner; onChange: (p: ProviderOwner) => void }) {
  const { t } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  const canRequest = profile.verification_status === 'UNVERIFIED' || profile.verification_status === 'REJECTED'
  return (
    <SectionCard id="verification" title={t('providerProfile.nav.verification')} description={t('providerProfile.verificationHint')} headingLevel={2}>
      <div className={styles.statusRow}>
        <span>{t('providerProfile.status')}:</span>
        <VerificationBadge status={profile.verification_status} />
        {profile.verification_status === 'PENDING' ? (
          <span className="text-caption cluster">
            <Icon name="clock" size={14} /> {t('providerProfile.pendingHint')}
          </span>
        ) : null}
      </div>
      {profile.verification_note ? (
        <Alert kind={profile.verification_status === 'REJECTED' || profile.verification_status === 'SUSPENDED' ? 'warning' : 'info'} title={t('providerProfile.statusNote')} className="stack" >
          {profile.verification_note}
        </Alert>
      ) : null}
      {error ? <Alert kind="error">{error}</Alert> : null}
      {canRequest ? (
        <FormActions>
          <ApiActionButton
            action={() => providersApi.requestVerification()}
            onSuccess={(updated) => {
              setError(null)
              onChange(updated)
            }}
            onError={(err) => setError(toErrorMessage(err))}
            pendingLabel={t('providerProfile.requestingVerification')}
            leading={<Icon name="shieldCheck" size={18} />}
          >
            {t('providerProfile.requestVerification')}
          </ApiActionButton>
        </FormActions>
      ) : null}
    </SectionCard>
  )
}

// ---- services -------------------------------------------------------------

const SERVICE_FIELDS = ['title', 'description', 'price', 'currency', 'duration_minutes', 'specialty'] as const

function ServicesSection({ specialties, services }: { specialties: Specialty[]; services: ReturnType<typeof useAsyncData<ServiceOffering[]>> }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
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
    if (duration.trim() && (!Number.isInteger(Number(duration)) || Number(duration) <= 0)) next.duration_minutes = t('validation.number')
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

  const refresh = () => {
    setRowError(null)
    services.reload()
  }

  return (
    <SectionCard id="services" title={t('providerProfile.services')} description={t('providerProfile.servicesIntro')} headingLevel={2}>
      {services.loading ? (
        <LoadingState testId="services-loading" />
      ) : services.error ? (
        <ErrorState error={services.error} onRetry={services.reload} />
      ) : (services.data ?? []).length === 0 ? (
        <EmptyState icon="tag" title={t('providerProfile.noServices')} testId="services-empty" />
      ) : (
        <ul className={styles.list}>
          {(services.data ?? []).map((s) => (
            <li key={s.id} className={styles.row} data-testid="service-row">
              <div className={styles.rowText}>
                <div className={styles.rowTitle}>{s.title}</div>
                <div className="text-caption">
                  {s.specialty ? name(specialties.find((sp) => sp.id === s.specialty)) : null}
                  {s.duration_minutes ? ` · ${t('providerDetail.duration', { minutes: s.duration_minutes })}` : ''}
                </div>
              </div>
              <span className={`${styles.price} ltr`}>
                {Number(s.price).toLocaleString(i18n.language)} {s.currency}
              </span>
              <div className={styles.rowActions}>
                <ApiActionButton
                  variant={s.is_active ? 'secondary' : 'ghost'}
                  size="sm"
                  action={() => providersApi.updateMyService(s.id, { is_active: !s.is_active })}
                  onSuccess={refresh}
                  onError={(error) => setRowError(toErrorMessage(error))}
                  aria-label={`${t('providerProfile.serviceActive')}: ${s.title}`}
                >
                  {s.is_active ? t('providerProfile.activeYes') : t('providerProfile.activeNo')}
                </ApiActionButton>
                <ApiActionButton
                  variant="ghost"
                  size="sm"
                  action={() => providersApi.deleteMyService(s.id)}
                  onSuccess={refresh}
                  onError={(error) => setRowError(toErrorMessage(error))}
                  pendingLabel={t('common.deleting')}
                  aria-label={`${t('common.delete')}: ${s.title}`}
                  leading={<Icon name="trash" size={16} />}
                >
                  {t('common.delete')}
                </ApiActionButton>
              </div>
            </li>
          ))}
        </ul>
      )}
      {rowError ? <Alert kind="error">{rowError}</Alert> : null}

      <form noValidate onSubmit={(e) => e.preventDefault()} style={{ marginBlockStart: 'var(--space-6)' }}>
        <h3 style={{ fontSize: 'var(--text-section)', marginBlockEnd: 'var(--space-4)' }}>{t('providerProfile.addService')}</h3>
        {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
        <TextField label={t('providerProfile.serviceTitle')} name="title" value={title} onChange={(e) => setTitle(e.target.value)} error={errors.fieldErrors.title} required />
        <Textarea label={t('providerProfile.serviceDescription')} optional name="description" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        <div className="grid-2">
          <TextField label={t('providerProfile.servicePrice')} name="price" dir="ltr" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} error={errors.fieldErrors.price} required />
          <Select label={t('providerProfile.serviceCurrency')} value={currency} onChange={(e) => setCurrency(e.target.value)}>
            <option value="IQD">IQD</option>
            <option value="USD">USD</option>
          </Select>
        </div>
        <div className="grid-2">
          <TextField
            label={t('providerProfile.serviceDuration')}
            optional
            name="duration_minutes"
            dir="ltr"
            inputMode="numeric"
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            error={errors.fieldErrors.duration_minutes}
          />
          <Select label={t('providers.specialty')} optional value={specialty} onChange={(e) => setSpecialty(e.target.value)}>
            <option value="">—</option>
            {specialties.map((s) => (
              <option key={s.id} value={s.id}>
                {name(s)}
              </option>
            ))}
          </Select>
        </div>
        <FormActions>
          <ApiActionButton
            type="submit"
            action={add}
            onSuccess={() => {
              setTitle('')
              setDescription('')
              setPrice('')
              setDuration('')
              setSpecialty('')
              refresh()
            }}
            onError={(error) => {
              if (!(error instanceof ClientValidationError)) errors.applyApiError(error)
            }}
            leading={<Icon name="plus" size={18} />}
          >
            {t('common.add')}
          </ApiActionButton>
        </FormActions>
      </form>
    </SectionCard>
  )
}

// ---- memberships ----------------------------------------------------------

function MembershipsSection({ profile, memberships }: { profile: ProviderOwner; memberships: ReturnType<typeof useAsyncData<Membership[]>> }) {
  const { t } = useTranslation()
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

  const refresh = () => {
    setRowError(null)
    memberships.reload()
  }
  const act = (m: Membership, action: 'accept' | 'reject' | 'end') => () => providersApi.membershipAction(m.id, action)
  const tone = (status: Membership['status']) => (status === 'ACTIVE' ? 'success' : status === 'PENDING' ? 'warning' : 'neutral')

  return (
    <SectionCard
      id="memberships"
      title={t('providerProfile.memberships')}
      description={isPractitioner ? t('providerProfile.membershipsIntroPractitioner') : t('providerProfile.membershipsIntroFacility')}
      headingLevel={2}
    >
      {memberships.loading ? (
        <LoadingState testId="memberships-loading" />
      ) : memberships.error ? (
        <ErrorState error={memberships.error} onRetry={memberships.reload} />
      ) : (memberships.data ?? []).length === 0 ? (
        <EmptyState icon="users" title={t('providerProfile.noMemberships')} testId="memberships-empty" />
      ) : (
        <ul className={styles.list}>
          {(memberships.data ?? []).map((m) => {
            const other = m.my_side === 'PRACTITIONER' ? m.facility : m.practitioner
            return (
              <li key={m.id} className={styles.row} data-testid="membership-row">
                <div className={styles.rowText}>
                  <div className={styles.rowTitle}>
                    <Link to={`/providers/${other.id}`}>{other.display_name}</Link>
                  </div>
                  <div className="text-caption">
                    {t(`providerTypes.${other.provider_type}`)}
                    {m.role_title ? ` · ${m.role_title}` : ''}
                  </div>
                </div>
                <Badge tone={tone(m.status)}>{t(`membershipStatus.${m.status}`)}</Badge>
                <div className={styles.rowActions}>
                  {m.status === 'PENDING' && m.can_accept ? (
                    <ApiActionButton size="sm" action={act(m, 'accept')} onSuccess={refresh} onError={(error) => setRowError(toErrorMessage(error))} leading={<Icon name="check" size={16} />}>
                      {t('providerProfile.accept')}
                    </ApiActionButton>
                  ) : null}
                  {m.status === 'PENDING' ? (
                    <ApiActionButton variant="ghost" size="sm" action={act(m, 'reject')} onSuccess={refresh} onError={(error) => setRowError(toErrorMessage(error))}>
                      {m.can_accept ? t('providerProfile.reject') : t('providerProfile.withdraw')}
                    </ApiActionButton>
                  ) : null}
                  {m.status === 'ACTIVE' ? (
                    <ApiActionButton variant="ghost" size="sm" action={act(m, 'end')} onSuccess={refresh} onError={(error) => setRowError(toErrorMessage(error))}>
                      {t('providerProfile.end')}
                    </ApiActionButton>
                  ) : null}
                </div>
              </li>
            )
          })}
        </ul>
      )}
      {rowError ? <Alert kind="error">{rowError}</Alert> : null}

      <form noValidate onSubmit={(e) => e.preventDefault()} style={{ marginBlockStart: 'var(--space-6)' }}>
        <h3 style={{ fontSize: 'var(--text-section)', marginBlockEnd: 'var(--space-4)' }}>
          {isPractitioner ? t('providerProfile.requestTitlePractitioner') : t('providerProfile.requestTitleFacility')}
        </h3>
        {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
        <div className="grid-2">
          <TextField
            label={t('providerProfile.counterpartId')}
            name="counterpart"
            dir="ltr"
            hint={t('providerProfile.counterpartHint')}
            value={counterpart}
            onChange={(e) => setCounterpart(e.target.value)}
            error={errors.fieldErrors.counterpart}
            required
          />
          <TextField label={t('providerProfile.roleTitle')} optional name="role_title" value={roleTitle} onChange={(e) => setRoleTitle(e.target.value)} error={errors.fieldErrors.role_title} />
        </div>
        <FormActions>
          <ApiActionButton
            type="submit"
            action={request}
            onSuccess={() => {
              setCounterpart('')
              setRoleTitle('')
              refresh()
            }}
            onError={(error) => {
              if (!(error instanceof ClientValidationError)) errors.applyApiError(error)
            }}
            leading={<Icon name="plus" size={18} />}
          >
            {t('providerProfile.requestMembership')}
          </ApiActionButton>
        </FormActions>
      </form>
    </SectionCard>
  )
}
