import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { offers as offersApi, providers as providersApi } from '../../api'
import type { ServiceOffering } from '../../api'
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
  Pagination,
  SectionCard,
  Select,
  Textarea,
  TextField,
  LinkButton,
  useFormErrors,
} from '../../design-system'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'
import { ClientValidationError, decimalOnly } from '../validation'

const PAGE_SIZE = 20

export function ProviderOffersPage() {
  const { t, i18n } = useTranslation()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const services = useAsyncData<ServiceOffering[]>((signal) => providersApi.listMyServices(signal), [])
  const offers = useAsyncData((signal) => offersApi.listProviderOffers(page, signal), [page])

  const [service, setService] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [price, setPrice] = useState('')
  const [startsAt, setStartsAt] = useState('')
  const [endsAt, setEndsAt] = useState('')
  const errors = useFormErrors(['service', 'title', 'description', 'offer_price', 'starts_at', 'ends_at'] as const)
  const active = (services.data ?? []).filter((item) => item.is_active)
  const chosen = active.find((item) => item.id === service)

  const create = async () => {
    const next: Record<string, string> = {}
    if (!service) next.service = t('validation.required')
    if (!title.trim()) next.title = t('validation.required')
    if (!price) next.offer_price = t('validation.required')
    else if (Number.isNaN(Number(price)) || Number(price) <= 0) next.offer_price = t('offers.invalidPrice')
    else if (chosen?.price != null && Number(price) >= Number(chosen.price)) {
      next.offer_price = t('offers.priceBelowService', { price: Number(chosen.price).toLocaleString(i18n.language) })
    }
    const start = new Date(startsAt)
    const end = new Date(endsAt)
    if (!startsAt) next.starts_at = t('validation.required')
    if (!endsAt) next.ends_at = t('validation.required')
    else if (Number.isNaN(end.getTime()) || end.getTime() <= Date.now()) next.ends_at = t('offers.endInFuture')
    else if (startsAt && end <= start) next.ends_at = t('offers.invalidWindow')
    if (Object.keys(next).length) {
      errors.setFieldErrors(next)
      throw new ClientValidationError()
    }
    errors.setFieldErrors({})
    return offersApi.createProviderOffer({
      service,
      title: title.trim(),
      description: description.trim(),
      offer_price: price,
      starts_at: start.toISOString(),
      ends_at: end.toISOString(),
    })
  }

  return (
    <Container width="xl">
      <PageHeader
        eyebrow={<><Icon name="tag" size={16} />{t('modules.offers')}</>}
        title={t('offers.manageTitle')}
        description={t('offers.manageIntro')}
      />
      <PageStack>
        <SectionCard title={t('offers.createTitle')} headingLevel={2}>
          {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
          {services.loading ? (
            <LoadingState />
          ) : services.error ? (
            <ErrorState error={services.error} onRetry={services.reload} />
          ) : active.length === 0 ? (
            <EmptyState
              icon="tag"
              title={t('offers.noServicesTitle')}
              action={<LinkButton to="/provider/profile">{t('offers.addService')}</LinkButton>}
              testId="offers-no-services"
            >
              {t('offers.noServicesHint')}
            </EmptyState>
          ) : (
            <form noValidate onSubmit={(event) => event.preventDefault()} data-testid="offer-form">
              <div className="grid-2">
                <Select
                  label={t('offers.service')}
                  value={service}
                  onChange={(event) => setService(event.target.value)}
                  error={errors.fieldErrors.service}
                  hint={chosen?.price != null ? t('offers.servicePrice', { price: Number(chosen.price).toLocaleString(i18n.language), currency: chosen.currency }) : undefined}
                  required
                >
                  <option value="">{t('offers.chooseService')}</option>
                  {active.map((item) => (
                    <option key={item.id} value={item.id}>{item.title}</option>
                  ))}
                </Select>
                <TextField label={t('offers.title')} value={title} maxLength={150} onChange={(event) => setTitle(event.target.value)} error={errors.fieldErrors.title} required />
              </div>
              <Textarea label={t('offers.description')} optional rows={2} maxLength={1000} value={description} onChange={(event) => setDescription(event.target.value)} error={errors.fieldErrors.description} />
              <div className="grid-2">
                <TextField
                  label={t('offers.offerPrice')}
                  dir="ltr"
                  inputMode="decimal"
                  value={price}
                  onChange={(event) => setPrice(decimalOnly(event.target.value))}
                  error={errors.fieldErrors.offer_price}
                  required
                />
                <span />
              </div>
              <div className="grid-2">
                <TextField label={t('offers.startsAt')} type="datetime-local" dir="ltr" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} error={errors.fieldErrors.starts_at} required />
                <TextField label={t('offers.endsAt')} type="datetime-local" dir="ltr" value={endsAt} min={startsAt || undefined} onChange={(event) => setEndsAt(event.target.value)} error={errors.fieldErrors.ends_at} required />
              </div>
              <FormActions>
                <ApiActionButton
                  type="submit"
                  action={create}
                  onSuccess={() => {
                    setService('')
                    setTitle('')
                    setDescription('')
                    setPrice('')
                    setStartsAt('')
                    setEndsAt('')
                    errors.setFieldErrors({})
                    errors.setFormError(null)
                    offers.reload()
                  }}
                  onError={(err) => {
                    if (!(err instanceof ClientValidationError)) errors.applyApiError(err)
                  }}
                  leading={<Icon name="plus" size={18} />}
                >
                  {t('offers.create')}
                </ApiActionButton>
              </FormActions>
            </form>
          )}
        </SectionCard>

        <SectionCard title={t('offers.myOffers')} headingLevel={2}>
          {offers.loading ? (
            <LoadingState />
          ) : offers.error ? (
            <ErrorState error={offers.error} onRetry={offers.reload} />
          ) : (offers.data?.results ?? []).length === 0 ? (
            <EmptyState icon="tag" title={t('offers.empty')} />
          ) : (
            <div className="stack">
              {(offers.data?.results ?? []).map((offer) => {
                const expired = new Date(offer.ends_at).getTime() <= Date.now()
                return (
                  <SectionCard
                    key={offer.id}
                    title={offer.title}
                    description={offer.service_title_snapshot}
                    headingLevel={3}
                    actions={
                      <Badge tone={offer.is_active && !expired ? 'success' : 'neutral'}>
                        {expired ? t('offers.expired') : offer.is_active ? t('offers.active') : t('offers.inactive')}
                      </Badge>
                    }
                  >
                    {offer.description ? <p className="text-secondary prewrap">{offer.description}</p> : null}
                    <p className="text-caption ltr">
                      {Number(offer.original_price_snapshot).toLocaleString(i18n.language)}
                      {' → '}
                      {Number(offer.offer_price).toLocaleString(i18n.language)} {offer.currency_snapshot}
                    </p>
                    <p className="text-caption">
                      {new Date(offer.starts_at).toLocaleString(i18n.language)} — {new Date(offer.ends_at).toLocaleString(i18n.language)}
                    </p>
                    {offer.is_active && !expired ? (
                      <FormActions>
                        <ApiActionButton
                          size="sm"
                          variant="ghost"
                          action={() => offersApi.updateProviderOffer(offer.id, { is_active: false })}
                          onSuccess={() => offers.reload()}
                          onError={(err) => errors.setFormError(toErrorMessage(err))}
                        >
                          {t('offers.deactivate')}
                        </ApiActionButton>
                      </FormActions>
                    ) : null}
                  </SectionCard>
                )
              })}
            </div>
          )}
          {offers.data ? (
            <Pagination
              page={page}
              total={Math.max(1, Math.ceil(offers.data.count / PAGE_SIZE))}
              hasNext={offers.data.next !== null}
              hasPrevious={offers.data.previous !== null}
              onChange={(next) => setParams(next > 1 ? { page: String(next) } : {})}
            />
          ) : null}
        </SectionCard>
      </PageStack>
    </Container>
  )
}
