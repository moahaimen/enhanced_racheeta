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
} from '../../design-system'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'

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
  const [error, setError] = useState<string | null>(null)

  const create = async () => {
    if (!service || !title.trim() || !price || !startsAt || !endsAt) {
      throw new Error(t('validation.required'))
    }
    const start = new Date(startsAt)
    const end = new Date(endsAt)
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
      throw new Error(t('offers.invalidWindow'))
    }
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
          {error ? <Alert kind="error">{error}</Alert> : null}
          {services.loading ? (
            <LoadingState />
          ) : services.error ? (
            <ErrorState error={services.error} onRetry={services.reload} />
          ) : (
            <form noValidate onSubmit={(event) => event.preventDefault()}>
              <div className="grid-2">
                <Select label={t('offers.service')} value={service} onChange={(event) => setService(event.target.value)}>
                  <option value="">—</option>
                  {(services.data ?? []).filter((item) => item.is_active).map((item) => (
                    <option key={item.id} value={item.id}>{item.title}</option>
                  ))}
                </Select>
                <TextField label={t('offers.title')} value={title} onChange={(event) => setTitle(event.target.value)} />
              </div>
              <Textarea label={t('offers.description')} optional rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
              <div className="grid-2">
                <TextField label={t('offers.offerPrice')} dir="ltr" inputMode="decimal" value={price} onChange={(event) => setPrice(event.target.value)} />
                <span />
              </div>
              <div className="grid-2">
                <TextField label={t('offers.startsAt')} type="datetime-local" dir="ltr" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} />
                <TextField label={t('offers.endsAt')} type="datetime-local" dir="ltr" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} />
              </div>
              <FormActions>
                <ApiActionButton
                  type="submit"
                  action={create}
                  onSuccess={() => {
                    setTitle('')
                    setDescription('')
                    setPrice('')
                    setStartsAt('')
                    setEndsAt('')
                    setError(null)
                    offers.reload()
                  }}
                  onError={(err) => setError(toErrorMessage(err))}
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
                          onError={(err) => setError(toErrorMessage(err))}
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
