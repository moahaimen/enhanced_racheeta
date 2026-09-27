import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { providers as providersApi, reservations as reservationsApi } from '../../api'
import type { ReservationProvider, ReservationStatus, ServiceOffering } from '../../api'
import {
  Alert,
  ApiActionButton,
  Badge,
  Container,
  EmptyState,
  ErrorState,
  FormActions,
  Icon,
  LoadingState,
  PageHeader,
  PageStack,
  SectionCard,
  Select,
  TextField,
} from '../../design-system'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'
import styles from './ReservationsPage.module.css'

function statusTone(status: ReservationStatus) {
  if (status === 'CONFIRMED' || status === 'COMPLETED') return 'success' as const
  if (status === 'PENDING') return 'warning' as const
  return 'neutral' as const
}

export function ProviderReservationsPage() {
  const { t } = useTranslation()
  const services = useAsyncData<ServiceOffering[]>((signal) => providersApi.listMyServices(signal), [])
  const slots = useAsyncData((signal) => reservationsApi.listProviderAvailability(1, signal), [])
  const reservations = useAsyncData((signal) => reservationsApi.listProviderReservations(1, signal), [])

  return (
    <Container width="xl">
      <PageHeader
        eyebrow={<><Icon name="calendar" size={16} />{t('nav.providerReservations')}</>}
        title={t('providerReservations.title')}
        description={t('providerReservations.intro')}
      />
      <PageStack>
        <AvailabilityBlock services={services} slots={slots} />
        <ReceivedReservationsBlock reservations={reservations} />
      </PageStack>
    </Container>
  )
}

function AvailabilityBlock({
  services,
  slots,
}: {
  services: ReturnType<typeof useAsyncData<ServiceOffering[]>>
  slots: ReturnType<typeof useAsyncData<Awaited<ReturnType<typeof reservationsApi.listProviderAvailability>>>>
}) {
  const { t, i18n } = useTranslation()
  const [service, setService] = useState('')
  const [startsAt, setStartsAt] = useState('')
  const [error, setError] = useState<string | null>(null)

  const create = async () => {
    if (!service || !startsAt) throw new Error(t('validation.required'))
    const date = new Date(startsAt)
    if (Number.isNaN(date.getTime())) throw new Error(t('providerReservations.invalidDate'))
    return reservationsApi.createProviderAvailability(service, date.toISOString())
  }

  return (
    <SectionCard title={t('providerReservations.availabilityTitle')} description={t('providerReservations.availabilityIntro')} headingLevel={2}>
      {error ? <Alert kind="error">{error}</Alert> : null}
      {services.loading ? (
        <LoadingState />
      ) : services.error ? (
        <ErrorState error={services.error} onRetry={services.reload} />
      ) : (
        <form noValidate onSubmit={(event) => event.preventDefault()}>
          <div className={styles.formGrid}>
            <Select label={t('providerReservations.service')} value={service} onChange={(event) => setService(event.target.value)}>
              <option value="">—</option>
              {(services.data ?? []).filter((item) => item.is_active && item.duration_minutes).map((item) => (
                <option key={item.id} value={item.id}>{item.title}</option>
              ))}
            </Select>
            <TextField
              label={t('providerReservations.startsAt')}
              type="datetime-local"
              value={startsAt}
              onChange={(event) => setStartsAt(event.target.value)}
              dir="ltr"
            />
          </div>
          <FormActions>
            <ApiActionButton
              type="submit"
              action={create}
              onSuccess={() => {
                setStartsAt('')
                setError(null)
                slots.reload()
              }}
              onError={(err) => setError(toErrorMessage(err))}
              leading={<Icon name="plus" size={18} />}
              pendingLabel={t('common.creating')}
            >
              {t('providerReservations.addSlot')}
            </ApiActionButton>
          </FormActions>
        </form>
      )}

      <div style={{ marginBlockStart: 'var(--space-5)' }}>
        {slots.loading ? (
          <LoadingState />
        ) : slots.error ? (
          <ErrorState error={slots.error} onRetry={slots.reload} />
        ) : (slots.data?.results ?? []).length === 0 ? (
          <EmptyState icon="calendar" title={t('providerReservations.noSlots')} />
        ) : (
          <ul className={styles.list}>
            {(slots.data?.results ?? []).map((slot) => (
              <li key={slot.id} className={styles.row}>
                <div className={styles.rowHead}>
                  <div>
                    <div className={styles.title}>{slot.service.title}</div>
                    <div className="text-caption">{new Date(slot.starts_at).toLocaleString(i18n.language)}</div>
                  </div>
                  <Badge tone={slot.is_active ? 'success' : 'neutral'}>
                    {slot.is_active ? t('providerReservations.active') : t('providerReservations.inactive')}
                  </Badge>
                </div>
                {slot.is_active ? (
                  <div className={styles.actions}>
                    <ApiActionButton
                      size="sm"
                      variant="ghost"
                      action={() => reservationsApi.deleteProviderAvailability(slot.id)}
                      onSuccess={() => slots.reload()}
                      onError={(err) => setError(toErrorMessage(err))}
                      pendingLabel={t('common.deleting')}
                    >
                      {t('providerReservations.deactivate')}
                    </ApiActionButton>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </SectionCard>
  )
}

function ReceivedReservationsBlock({
  reservations,
}: {
  reservations: ReturnType<typeof useAsyncData<Awaited<ReturnType<typeof reservationsApi.listProviderReservations>>>>
}) {
  const { t } = useTranslation()
  if (reservations.loading) return <LoadingState />
  if (reservations.error) return <ErrorState error={reservations.error} onRetry={reservations.reload} />
  if ((reservations.data?.results ?? []).length === 0) {
    return <SectionCard title={t('providerReservations.receivedTitle')} headingLevel={2}><EmptyState icon="calendar" title={t('providerReservations.noReservations')} /></SectionCard>
  }
  return (
    <SectionCard title={t('providerReservations.receivedTitle')} description={t('providerReservations.receivedIntro')} headingLevel={2}>
      <ul className={styles.list}>
        {(reservations.data?.results ?? []).map((reservation) => (
          <li key={reservation.id} className={styles.row}>
            <ProviderReservationRow reservation={reservation} reload={reservations.reload} />
          </li>
        ))}
      </ul>
    </SectionCard>
  )
}

function ProviderReservationRow({ reservation, reload }: { reservation: ReservationProvider; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  const transition = (status: ReservationStatus) => () =>
    reservationsApi.transitionProviderReservation(reservation.id, status)
  const hasStarted = new Date(reservation.starts_at).getTime() <= Date.now()

  return (
    <>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <div className={styles.rowHead}>
        <div>
          <div className={styles.title}>{reservation.patient.full_name}</div>
          <div className="text-caption">{reservation.service_title_snapshot}</div>
        </div>
        <Badge tone={statusTone(reservation.status)}>{t(`reservationStatus.${reservation.status}`)}</Badge>
      </div>
      <div className={styles.meta}>
        <span><Icon name="calendar" size={14} /> {new Date(reservation.starts_at).toLocaleString(i18n.language)}</span>
        <span><Icon name="clock" size={14} /> {t('providerDetail.duration', { minutes: reservation.duration_minutes_snapshot })}</span>
      </div>
      {reservation.patient_note ? <p className="text-secondary prewrap">{reservation.patient_note}</p> : null}
      <div className={styles.actions}>
        {reservation.status === 'PENDING' ? (
          <>
            <TransitionButton label={t('common.accept')} action={transition('CONFIRMED')} reload={reload} setError={setError} />
            <TransitionButton label={t('common.reject')} action={transition('REJECTED')} reload={reload} setError={setError} variant="ghost" />
            <TransitionButton label={t('common.cancel')} action={transition('CANCELLED')} reload={reload} setError={setError} variant="ghost" />
          </>
        ) : null}
        {reservation.status === 'CONFIRMED' ? (
          <>
            {hasStarted ? (
              <>
                <TransitionButton label={t('providerReservations.complete')} action={transition('COMPLETED')} reload={reload} setError={setError} />
                <TransitionButton label={t('providerReservations.noShow')} action={transition('NO_SHOW')} reload={reload} setError={setError} variant="ghost" />
              </>
            ) : null}
            <TransitionButton label={t('common.cancel')} action={transition('CANCELLED')} reload={reload} setError={setError} variant="ghost" />
          </>
        ) : null}
      </div>
    </>
  )
}

function TransitionButton({
  label,
  action,
  reload,
  setError,
  variant,
}: {
  label: string
  action: () => Promise<ReservationProvider>
  reload: () => void
  setError: (value: string | null) => void
  variant?: 'ghost'
}) {
  return (
    <ApiActionButton
      size="sm"
      variant={variant}
      action={action}
      onSuccess={() => {
        setError(null)
        reload()
      }}
      onError={(err) => setError(toErrorMessage(err))}
    >
      {label}
    </ApiActionButton>
  )
}
