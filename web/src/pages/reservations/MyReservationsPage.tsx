import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { chat as chatApi, reservations as reservationsApi, reviews as reviewsApi } from '../../api'
import type { ReservationPatient, ReservationStatus } from '../../api'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Badge,
  Container,
  EmptyState,
  FormActions,
  Icon,
  LinkButton,
  PageHeader,
  PageStack,
  Pagination,
  SectionCard,
  Select,
  Textarea,
} from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import styles from './ReservationsPage.module.css'

const PAGE_SIZE = 20

function statusTone(status: ReservationStatus) {
  if (status === 'CONFIRMED' || status === 'COMPLETED') return 'success' as const
  if (status === 'PENDING') return 'warning' as const
  return 'neutral' as const
}

export function MyReservationsPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const goTo = (next: number) => setParams(next > 1 ? { page: String(next) } : {})

  return (
    <Container width="xl">
      <PageHeader
        eyebrow={<><Icon name="calendar" size={16} />{t('modules.reservations')}</>}
        title={t('reservations.title')}
        description={t('reservations.intro')}
        actions={<LinkButton to="/providers" leading={<Icon name="search" size={18} />}>{t('reservations.findProvider')}</LinkButton>}
      />
      <PageStack>
        <AsyncPage load={(signal) => reservationsApi.listMyReservations(page, signal)} deps={[page]}>
          {(result, reload) =>
            result.results.length === 0 ? (
              <div className="card-block">
                <EmptyState
                  icon="calendar"
                  title={page > 1 ? t('reservations.emptyPage') : t('reservations.empty')}
                  action={<LinkButton to="/providers">{t('reservations.findProvider')}</LinkButton>}
                />
              </div>
            ) : (
              <>
                <p className="text-caption">{t('reservations.count', { count: result.count })}</p>
                {result.results.map((reservation) => (
                  <ReservationCard key={reservation.id} reservation={reservation} reload={reload} />
                ))}
                <Pagination
                  page={page}
                  total={Math.max(1, Math.ceil(result.count / PAGE_SIZE))}
                  hasNext={result.next !== null}
                  hasPrevious={result.previous !== null}
                  onChange={goTo}
                />
              </>
            )
          }
        </AsyncPage>
      </PageStack>
    </Container>
  )
}

function ReservationCard({ reservation, reload }: { reservation: ReservationPatient; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const canCancel =
    ['PENDING', 'CONFIRMED'].includes(reservation.status) &&
    new Date(reservation.starts_at).getTime() > Date.now()

  return (
    <SectionCard
      title={
        reservation.provider_id ? (
          <Link to={`/providers/${reservation.provider_id}`}>{reservation.provider_name_snapshot}</Link>
        ) : (
          reservation.provider_name_snapshot
        )
      }
      description={reservation.service_title_snapshot}
      headingLevel={2}
      actions={<Badge tone={statusTone(reservation.status)}>{t(`reservationStatus.${reservation.status}`)}</Badge>}
    >
      {error ? <Alert kind="error">{error}</Alert> : null}
      <div className={styles.meta}>
        <span><Icon name="calendar" size={14} /> {new Date(reservation.starts_at).toLocaleString(i18n.language)}</span>
        <span><Icon name="clock" size={14} /> {t('providerDetail.duration', { minutes: reservation.duration_minutes_snapshot })}</span>
        <span className="ltr">{Number(reservation.price_snapshot).toLocaleString(i18n.language)} {reservation.currency_snapshot}</span>
      </div>
      {reservation.patient_note ? <p className="text-secondary prewrap">{reservation.patient_note}</p> : null}
      {reservation.transitions.length > 0 ? (
        <ol className={styles.history}>
          {reservation.transitions.map((transition, index) => (
            <li key={index}>
              {t(`reservationStatus.${transition.to_status}`)} · {new Date(transition.created_at).toLocaleString(i18n.language)}
              {transition.reason ? ` — ${transition.reason}` : ''}
            </li>
          ))}
        </ol>
      ) : null}
      {reservation.status === 'COMPLETED' && reservation.review_id ? (
        <Badge tone="outline">{t('reviews.alreadyReviewed')}</Badge>
      ) : null}
      {reservation.status === 'COMPLETED' && !reservation.review_id && reservation.provider_id ? (
        // A review needs a provider to attach to: a completed reservation whose provider
        // was deleted stays visible through its snapshots, but cannot be reviewed.
        <ReviewForm reservationId={reservation.id} reload={reload} setError={setError} />
      ) : null}
      <div className={styles.actions}>
        <ApiActionButton
          variant="secondary"
          size="sm"
          action={() => chatApi.openReservationConversation(reservation.id)}
          onSuccess={(conversation) => navigate(`/messages/${conversation.id}`)}
          onError={(err) => setError(toErrorMessage(err))}
          pendingLabel={t('messages.opening')}
          leading={<Icon name="mail" size={16} />}
        >
          {t('messages.messageProvider')}
        </ApiActionButton>
      </div>
      {canCancel ? (
        <div className={styles.actions}>
          <ApiActionButton
            variant="ghost"
            size="sm"
            action={() => reservationsApi.cancelMyReservation(reservation.id)}
            onSuccess={reload}
            onError={(err) => setError(toErrorMessage(err))}
            pendingLabel={t('reservations.cancelling')}
          >
            {t('reservations.cancel')}
          </ApiActionButton>
        </div>
      ) : null}
    </SectionCard>
  )
}


function ReviewForm({
  reservationId,
  reload,
  setError,
}: {
  reservationId: string
  reload: () => void
  setError: (value: string | null) => void
}) {
  const { t } = useTranslation()
  const [rating, setRating] = useState('5')
  const [comment, setComment] = useState('')

  return (
    <div className="stack" style={{ marginBlockStart: 'var(--space-4)' }}>
      <strong>{t('reviews.leaveReview')}</strong>
      <div className="grid-2">
        <Select label={t('reviews.rating')} value={rating} onChange={(event) => setRating(event.target.value)}>
          {[5, 4, 3, 2, 1].map((value) => (
            <option key={value} value={String(value)}>{value}/5</option>
          ))}
        </Select>
        <Textarea
          label={t('reviews.comment')}
          optional
          rows={2}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
        />
      </div>
      <FormActions>
        <ApiActionButton
          size="sm"
          action={() => reviewsApi.createReview(reservationId, Number(rating), comment)}
          onSuccess={() => {
            setError(null)
            reload()
          }}
          onError={(err) => setError(toErrorMessage(err))}
        >
          {t('reviews.submit')}
        </ApiActionButton>
      </FormActions>
    </div>
  )
}
