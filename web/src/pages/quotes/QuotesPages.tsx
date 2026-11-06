import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { commerce, reference, workspaces as api } from '../../api'
import type { DeliveryDefaults, Governorate, Quote, QuoteStatus, StorePaymentMethod } from '../../api'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Badge,
  Button,
  Container,
  EmptyState,
  FormActions,
  Icon,
  PageHeader,
  PageStack,
  PhoneField,
  SectionCard,
  Select,
  TextField,
  Textarea,
  type BadgeTone,
} from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import { pickScript, useLocalizedName } from '../../i18n/localized'
import { newIdempotencyKey } from '../market/money'
import { normalizeIraqiPhone } from '../validation'

const TONE: Record<QuoteStatus, BadgeTone> = {
  REQUESTED: 'warning',
  QUOTED: 'brand',
  ACCEPTED: 'success',
  DECLINED: 'neutral',
  WITHDRAWN: 'neutral',
  ORDERED: 'success',
  EXPIRED: 'neutral',
}

function QuoteCard({ quote, merchantView, children }: { quote: Quote; merchantView?: boolean; children?: React.ReactNode }) {
  const { t, i18n } = useTranslation()
  const counterpart = merchantView ? quote.requester.display_name : quote.company.name
  return (
    <SectionCard
      title={pickScript(quote.product.title, i18n.language)}
      description={t('quotes.from', { name: pickScript(counterpart, i18n.language) })}
      headingLevel={2}
      actions={<Badge tone={TONE[quote.status]}>{t(`quotes.status.${quote.status}`)}</Badge>}
    >
      <div className="cluster text-caption">
        <span>{t('store.quantity')}: {quote.quantity}</span>
        {quote.expires_at && ['QUOTED', 'ACCEPTED'].includes(quote.status) ? (
          <span>{t('quotes.validUntil', { date: new Date(quote.expires_at).toLocaleDateString(i18n.language) })}</span>
        ) : null}
        {quote.quoted_unit_price ? (
          <strong className="ltr">
            {t('quotes.unitPrice')}: {Number(quote.quoted_unit_price).toLocaleString(i18n.language)} {quote.quoted_currency}
          </strong>
        ) : null}
        <time dateTime={quote.created_at}>{new Date(quote.created_at).toLocaleDateString(i18n.language)}</time>
      </div>
      {quote.message ? <p className="text-secondary prewrap">{quote.message}</p> : null}
      {quote.quoted_note ? <p className="prewrap">{quote.quoted_note}</p> : null}
      {children}
    </SectionCard>
  )
}

/** /quotes — a verified provider's own quote requests (B2B, targeted products only). */
export function MyQuotesPage() {
  const { t } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  return (
    <Container width="xl">
      <PageHeader eyebrow={<><Icon name="tag" size={16} />{t('nav.marketplace')}</>} title={t('quotes.title')} description={t('quotes.intro')} />
      <PageStack>
        {error ? <Alert kind="error">{error}</Alert> : null}
        <AsyncPage load={(signal) => api.listMyQuotes(1, signal)}>
          {(page, reload) =>
            page.results.length === 0 ? (
              <div className="card-block"><EmptyState icon="tag" title={t('quotes.none')} /></div>
            ) : (
              page.results.map((quote) => {
                const close = (outcome: 'ACCEPTED' | 'DECLINED' | 'WITHDRAWN') => (
                  <ApiActionButton
                    key={outcome}
                    size="sm"
                    variant={outcome === 'ACCEPTED' ? 'primary' : 'ghost'}
                    action={() => api.closeMyQuote(quote.id, outcome)}
                    onSuccess={reload}
                    onError={(e) => setError(toErrorMessage(e))}
                  >
                    {t(outcome === 'ACCEPTED' ? 'quotes.accept' : outcome === 'DECLINED' ? 'quotes.decline' : 'quotes.withdraw')}
                  </ApiActionButton>
                )
                return (
                  <QuoteCard key={quote.id} quote={quote}>
                    <div className="cluster">
                      {quote.status === 'QUOTED' ? [close('ACCEPTED'), close('DECLINED')] : null}
                      {quote.status === 'REQUESTED' || quote.status === 'QUOTED' ? close('WITHDRAWN') : null}
                    </div>
                    {quote.status === 'ACCEPTED' ? <QuoteOrder quote={quote} onDone={reload} onError={(m) => setError(m)} /> : null}
                    {quote.status === 'ORDERED' ? <p className="text-caption"><Icon name="checkCircle" size={14} /> {t('quotes.orderedHint')}</p> : null}
                  </QuoteCard>
                )
              })
            )
          }
        </AsyncPage>
      </PageStack>
    </Container>
  )
}

/** /merchant/quotes[?company=] — requests received by a business the caller owns or works for. */
export function MerchantQuotesPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const company = params.get('company') ?? undefined
  const [error, setError] = useState<string | null>(null)
  return (
    <Container width="xl">
      <PageHeader eyebrow={<><Icon name="tag" size={16} />{t('nav.companyWorkspace')}</>} title={t('quotes.incoming')} />
      <PageStack>
        {error ? <Alert kind="error">{error}</Alert> : null}
        <AsyncPage load={(signal) => api.listMerchantQuotes(company, 1, signal)} deps={[company]}>
          {(page, reload) =>
            page.results.length === 0 ? (
              <div className="card-block"><EmptyState icon="tag" title={t('quotes.none')} /></div>
            ) : (
              page.results.map((quote) => (
                <QuoteCard key={quote.id} quote={quote} merchantView>
                  {quote.status === 'REQUESTED' ? (
                    <RespondForm quote={quote} company={company} onDone={reload} onError={setError} />
                  ) : null}
                </QuoteCard>
              ))
            )
          }
        </AsyncPage>
      </PageStack>
    </Container>
  )
}

function RespondForm({ quote, company, onDone, onError }: { quote: Quote; company?: string; onDone: () => void; onError: (m: string) => void }) {
  const { t } = useTranslation()
  const [price, setPrice] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    try {
      await api.respondQuote(quote.id, price, note, company)
      onDone()
    } catch (e) {
      onError(toErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <form onSubmit={submit} className="stack-sm">
      <TextField label={t('quotes.unitPrice')} type="number" min={0} step="0.01" required value={price} onChange={(e) => setPrice(e.target.value)} />
      <Textarea label={t('store.note')} optional maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
      <FormActions>
        <Button type="submit" size="sm" loading={busy}>{t('quotes.respond')}</Button>
        <ApiActionButton size="sm" variant="ghost" action={() => api.declineQuote(quote.id, company)} onSuccess={onDone} onError={(e) => onError(toErrorMessage(e))}>
          {t('quotes.decline')}
        </ApiActionButton>
      </FormActions>
    </form>
  )
}

/** Inline "request a quote" control for a targeted product (used on the product page). */
export function RequestQuoteForm({ productId }: { productId: string }) {
  const { t } = useTranslation()
  const [quantity, setQuantity] = useState('1')
  const [message, setMessage] = useState('')
  const [state, setState] = useState<{ ok?: boolean; error?: string }>({})
  const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    try {
      await api.requestQuote(productId, Number(quantity), message)
      setState({ ok: true })
    } catch (e) {
      setState({ error: toErrorMessage(e) })
    } finally {
      setBusy(false)
    }
  }
  if (state.ok) return <Alert kind="success">{t('quotes.requested')}</Alert>
  return (
    <form onSubmit={submit} className="stack-sm" data-testid="quote-form">
      {state.error ? <Alert kind="error">{state.error}</Alert> : null}
      <TextField label={t('store.quantity')} type="number" min={1} max={10000} required value={quantity} onChange={(e) => setQuantity(e.target.value)} />
      <Textarea label={t('quotes.message')} optional maxLength={1000} value={message} onChange={(e) => setMessage(e.target.value)} />
      <FormActions>
        <Button type="submit" loading={busy}>{t('quotes.request')}</Button>
      </FormActions>
    </form>
  )
}


/** Accepted quotation -> one order at the quoted price (same 20% snapshot, ledger and stock rules). */
function QuoteOrder({ quote, onDone, onError }: { quote: Quote; onDone: () => void; onError: (m: string) => void }) {
  const { t } = useTranslation()
  return (
    <AsyncPage
      load={async (signal) => {
        const [defaults, governorates] = await Promise.all([api.getDeliveryDefaults(signal), reference.listGovernorates(undefined, signal)])
        return { defaults, governorates }
      }}
    >
      {({ defaults, governorates }) => <QuoteOrderForm quote={quote} defaults={defaults} governorates={governorates} onDone={onDone} onError={onError} t={t} />}
    </AsyncPage>
  )
}

function QuoteOrderForm({ quote, defaults, governorates, onDone, onError, t }: {
  quote: Quote
  defaults: DeliveryDefaults
  governorates: Governorate[]
  onDone: () => void
  onError: (m: string) => void
  t: (key: string, options?: Record<string, unknown>) => string
}) {
  const name = useLocalizedName()
  const [governorate, setGovernorate] = useState(defaults.governorate ?? '')
  const [address, setAddress] = useState(defaults.address)
  const [phone, setPhone] = useState(defaults.phone)
  const [method, setMethod] = useState<StorePaymentMethod>('MANUAL_TRANSFER')
  const [busy, setBusy] = useState(false)
  const [key] = useState(newIdempotencyKey)
  const valid = Boolean(governorate) && address.trim().length >= 5 && Boolean(normalizeIraqiPhone(phone, { mobileOnly: true }))
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!valid) return
    setBusy(true)
    try {
      await commerce.orderFromQuote(quote.id, {
        idempotency_key: key,
        payment_method: method,
        governorate,
        address: address.trim(),
        phone: normalizeIraqiPhone(phone, { mobileOnly: true })!,
      })
      onDone()
    } catch (e) {
      onError(toErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }
  const total = Number(quote.quoted_unit_price ?? 0) * quote.quantity
  return (
    <form onSubmit={submit} className="stack-sm card-block" noValidate data-testid="quote-order-form">
      <strong>{t('quotes.orderTotal', { total: total.toLocaleString(), currency: quote.quoted_currency })}</strong>
      <Select label={t('store.governorate')} value={governorate} onChange={(e) => setGovernorate(e.target.value)}>
        <option value="">{t('store.chooseGovernorate')}</option>
        {governorates.map((g) => <option key={g.id} value={g.id}>{name(g)}</option>)}
      </Select>
      <TextField label={t('store.address')} maxLength={255} value={address} onChange={(e) => setAddress(e.target.value)} />
      <PhoneField label={t('store.phone')} value={phone} onChange={(e) => setPhone(e.target.value)} hint={t('validation.mobileHint')} />
      <Select label={t('store.payment')} value={method} onChange={(e) => setMethod(e.target.value as StorePaymentMethod)}>
        <option value="MANUAL_TRANSFER">{t('store.paymentMethods.MANUAL_TRANSFER')}</option>
        <option value="CASH_ON_DELIVERY">{t('store.paymentMethods.CASH_ON_DELIVERY')}</option>
      </Select>
      <FormActions>
        <Button type="submit" size="sm" loading={busy} disabled={!valid} leading={<Icon name="cart" size={14} />}>{t('quotes.orderNow')}</Button>
      </FormActions>
    </form>
  )
}
