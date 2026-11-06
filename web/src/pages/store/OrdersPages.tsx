import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { commerce, workspaces as api } from '../../api'
import type { Order, ReturnStatus } from '../../api'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Badge,
  Button,
  Container,
  EmptyState,
  Icon,
  LinkButton,
  PageHeader,
  PageStack,
  ProductImage,
  SectionCard,
  Select,
  TextField,
  Textarea,
} from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import { pickScript, useLocalizedName } from '../../i18n/localized'
import { useMoney } from '../market/money'
import { MoneyTable } from '../market/MoneyTable'
import { ORDER_TONE, PAYMENT_TONE, RETURN_TONE } from '../market/tones'
import { SellerNav } from '../market/SellerNav'
import { OrderTracker } from './OrderTracker'

/** One order: items, server amounts, status, tracker, returns/disputes/refunds history. */
export function OrderCard({ order, seller = false, children }: { order: Order; seller?: boolean; children?: ReactNode }) {
  const { t, i18n } = useTranslation()
  const money = useMoney()
  return (
    <SectionCard
      title={<span className="ltr">{order.number}</span>}
      description={pickScript(order.merchant.name, i18n.language)}
      headingLevel={3}
      actions={
        <span className="cluster">
          {order.channel === 'B2B' ? <Badge tone="brand">{t('market.b2b')}</Badge> : null}
          <Badge tone={ORDER_TONE[order.status]}>{t(`market.orderStatus.${order.status}`)}</Badge>
        </span>
      }
    >
      <ul className="stack-sm" style={{ margin: 0, padding: 0, listStyle: 'none' }}>
        {order.items.map((item) => (
          <li key={item.id} className="cluster" data-testid="order-item">
            <ProductImage src={item.image_url} alt="" size="sm" />
            <span>
              {pickScript(item.title_snapshot, i18n.language)} × {item.quantity}
              {item.refunded_quantity ? <> · <Badge tone="neutral">{t('market.refundedUnits', { count: item.refunded_quantity })}</Badge></> : null}
            </span>
            <span className="ltr text-caption">{money(item.buyer_paid, order.currency)}</span>
          </li>
        ))}
      </ul>
      <MoneyTable
        currency={order.currency}
        rows={[
          { label: t('market.listTotal'), value: order.list_total },
          { label: t('market.sellerDiscount'), value: order.seller_discount_total, minus: true, hidden: Number(order.seller_discount_total) === 0 },
          { label: t('market.racheetaDiscount'), value: order.platform_discount_total, minus: true, hidden: Number(order.platform_discount_total) === 0 },
          { label: t('market.buyerPays'), value: order.total, strong: !seller },
          { label: t('market.refunded'), value: order.refunded_total, minus: true, hidden: Number(order.refunded_total) === 0 },
          { label: t('market.commissionBase'), value: order.merchandise_net, hidden: !seller },
          { label: t('market.commission', { rate: Number(order.commission_rate ?? 20) }), value: order.commission_total, minus: true, hidden: !seller },
          { label: t('market.commissionReversed'), value: sum(order, 'refunded_commission'), hidden: !seller || sum(order, 'refunded_commission') === 0 },
          { label: t('market.sellerPayable'), value: order.seller_payable_total, strong: true, hidden: !seller },
          { label: t('market.payableReversed'), value: sum(order, 'refunded_seller_payable'), minus: true, hidden: !seller || sum(order, 'refunded_seller_payable') === 0 },
        ]}
      />
      <div className="cluster text-caption">
        <span>{t(`store.paymentMethods.${order.payment_method}`)}</span>
        <Badge tone={PAYMENT_TONE[order.payment_status]}>{t(`market.paymentStatus.${order.payment_status}`)}</Badge>
        {seller && order.settlement_state === 'ACCRUED' ? <Badge tone="success">{t('market.accrued')}</Badge> : null}
        {order.checkout_number ? <span className="ltr">{t('market.checkoutNo')} {order.checkout_number}</span> : null}
        {order.shipping_reference ? <span>{t('market.shippingRef')}: <span className="ltr">{order.shipping_reference}</span></span> : null}
        <time dateTime={order.created_at}>{new Date(order.created_at).toLocaleString(i18n.language)}</time>
      </div>
      <OrderTracker status={order.status} />
      {order.returns.map((r) => (
        <p key={r.id} className="text-caption" data-testid="order-return">
          <Icon name="refresh" size={14} /> {t('market.returnLabel')}: <Badge tone={RETURN_TONE[r.status]}>{t(`market.returnStatus.${r.status}`)}</Badge>{' '}
          {r.lines.map((l) => `${pickScript(l.title, i18n.language)} × ${l.quantity}`).join(', ')} — {r.reason}
        </p>
      ))}
      {order.disputes.map((d) => (
        <p key={d.id} className="text-caption" data-testid="order-dispute">
          <Icon name="alertCircle" size={14} /> {t('market.disputeLabel')}: <Badge tone={d.status === 'OPEN' ? 'warning' : 'neutral'}>{t(`market.disputeStatus.${d.status}`)}</Badge> {d.reason}
          {d.resolution_note ? ` — ${d.resolution_note}` : ''}
        </p>
      ))}
      {order.refunds.map((r) => (
        <p key={r.id} className="text-caption">
          <Icon name="checkCircle" size={14} /> {t('market.refundOf', { amount: money(r.amount, order.currency) })} — {r.reason}
        </p>
      ))}
      {children}
    </SectionCard>
  )
}

function sum(order: Order, field: 'refunded_commission' | 'refunded_seller_payable'): number {
  return order.items.reduce((total, item) => total + Number(item[field] ?? 0), 0)
}

const OPEN_RETURN: ReturnStatus[] = ['REQUESTED', 'APPROVED', 'RECEIVED']

/** /orders — the buyer's own orders, grouped by checkout (one checkout = one order per seller). */
export function MyOrdersPage() {
  const { t } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  return (
    <Container width="xl">
      <PageHeader
        eyebrow={<><Icon name="cart" size={16} />{t('nav.store')}</>}
        title={t('store.myOrders')}
        actions={<LinkButton to="/store">{t('nav.store')}</LinkButton>}
      />
      <PageStack>
        <Alert kind="info">{t('market.buyerInfo')}</Alert>
        {error ? <Alert kind="error">{error}</Alert> : null}
        <AsyncPage load={(signal) => api.listMyOrders(1, signal)}>
          {(page, reload) => {
            if (page.results.length === 0) {
              return <div className="card-block"><EmptyState icon="cart" title={t('store.noOrders')} /></div>
            }
            const groups = new Map<string, Order[]>()
            for (const order of page.results) {
              const key = order.checkout_number || order.number
              groups.set(key, [...(groups.get(key) ?? []), order])
            }
            const done = () => {
              setError(null)
              reload()
            }
            const fail = (e: unknown) => setError(toErrorMessage(e))
            return [...groups.entries()].map(([key, orders]) => (
              <section key={key} className="stack-sm" aria-label={key} data-testid="checkout-group">
                <h2 className="text-caption">
                  <Icon name="box" size={14} /> {t('market.checkoutNo')} <span className="ltr">{key}</span>
                  {orders.length > 1 ? ` · ${t('market.sellers', { count: orders.length })}` : ''}
                </h2>
                {orders.map((order) => (
                  <OrderCard key={order.id} order={order}>
                    <BuyerActions order={order} onDone={done} onError={fail} />
                  </OrderCard>
                ))}
              </section>
            ))
          }}
        </AsyncPage>
      </PageStack>
    </Container>
  )
}

function BuyerActions({ order, onDone, onError }: { order: Order; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const [form, setForm] = useState<'return' | 'dispute' | null>(null)
  const openReturn = order.returns.some((r) => OPEN_RETURN.includes(r.status))
  const openDispute = order.disputes.some((d) => d.status === 'OPEN')
  const inWindow = order.return_deadline ? new Date(order.return_deadline) > new Date() : false
  const returnable = ['DELIVERED', 'COMPLETED'].includes(order.status) && inWindow && !openReturn && order.items.some((i) => i.quantity > i.refunded_quantity)
  const disputable = ['SHIPPED', 'DELIVERED', 'COMPLETED'].includes(order.status) && !openDispute
  return (
    <div className="stack-sm">
      <div className="cluster">
        {order.status === 'PLACED' || order.status === 'CONFIRMED' ? (
          <ApiActionButton size="sm" variant="ghost" action={() => api.cancelMyOrder(order.id)} onSuccess={onDone} onError={onError}>
            {t('store.cancelOrder')}
          </ApiActionButton>
        ) : null}
        {order.status === 'SHIPPED' ? (
          <ApiActionButton size="sm" action={() => commerce.confirmDelivery(order.id)} onSuccess={onDone} onError={onError} leading={<Icon name="check" size={14} />}>
            {t('market.confirmReceived')}
          </ApiActionButton>
        ) : null}
        {returnable ? (
          <Button size="sm" variant="secondary" onClick={() => setForm(form === 'return' ? null : 'return')}>{t('market.requestReturn')}</Button>
        ) : null}
        {disputable ? (
          <Button size="sm" variant="ghost" onClick={() => setForm(form === 'dispute' ? null : 'dispute')}>{t('market.openDispute')}</Button>
        ) : null}
      </div>
      {order.return_deadline && ['DELIVERED', 'COMPLETED'].includes(order.status) ? (
        <p className="text-caption">{t('market.returnBy', { date: new Date(order.return_deadline).toLocaleDateString() })}</p>
      ) : null}
      {form === 'return' ? <ReturnForm order={order} onDone={() => { setForm(null); onDone() }} onError={onError} /> : null}
      {form === 'dispute' ? <DisputeForm order={order} onDone={() => { setForm(null); onDone() }} onError={onError} /> : null}
    </div>
  )
}

function ReturnForm({ order, onDone, onError }: { order: Order; onDone: () => void; onError: (e: unknown) => void }) {
  const { t, i18n } = useTranslation()
  const [qty, setQty] = useState<Record<string, number>>({})
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [invalid, setInvalid] = useState<string | null>(null)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const lines = Object.entries(qty).filter(([, q]) => q > 0).map(([item, quantity]) => ({ item, quantity }))
    if (!lines.length) return setInvalid(t('market.chooseItems'))
    if (reason.trim().length < 3) return setInvalid(t('market.giveReason'))
    setBusy(true)
    try {
      await commerce.requestReturn(order.id, lines, reason.trim())
      onDone()
    } catch (e) {
      onError(e)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form onSubmit={submit} className="stack-sm card-block" data-testid="return-form" noValidate>
      {invalid ? <Alert kind="warning">{invalid}</Alert> : null}
      {order.items.filter((i) => i.quantity > i.refunded_quantity).map((item) => (
        <Select key={item.id} label={pickScript(item.title_snapshot, i18n.language)} value={String(qty[item.id] ?? 0)} onChange={(e) => setQty({ ...qty, [item.id]: Number(e.target.value) })}>
          {Array.from({ length: item.quantity - item.refunded_quantity + 1 }, (_, n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </Select>
      ))}
      <Textarea label={t('market.reason')} required maxLength={500} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
      <Button type="submit" size="sm" loading={busy}>{t('market.sendReturn')}</Button>
    </form>
  )
}

function DisputeForm({ order, onDone, onError }: { order: Order; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (reason.trim().length < 3) return
    setBusy(true)
    try {
      await commerce.openDispute(order.id, reason.trim())
      onDone()
    } catch (e) {
      onError(e)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form onSubmit={submit} className="stack-sm card-block" data-testid="dispute-form" noValidate>
      <Textarea label={t('market.disputeReason')} required maxLength={1000} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} hint={t('market.disputeHint')} />
      <Button type="submit" size="sm" loading={busy} disabled={reason.trim().length < 3}>{t('market.sendDispute')}</Button>
    </form>
  )
}

/** /merchant/orders[?company=] — orders of a business the caller owns or works for. */
export function MerchantOrdersPage() {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const [params] = useSearchParams()
  const company = params.get('company') ?? undefined
  const status = params.get('status') ?? ''
  const [error, setError] = useState<string | null>(null)
  return (
    <Container width="xl">
      <PageHeader eyebrow={<><Icon name="cart" size={16} />{t('market.sellerCenter')}</>} title={t('store.merchantOrders')} description={t('market.sellerOrdersIntro')} />
      <SellerNav active="orders" />
      <PageStack>
        {error ? <Alert kind="error">{error}</Alert> : null}
        <AsyncPage load={(signal) => api.listMerchantOrders(company, 1, signal)} deps={[company]}>
          {(page, reload) => {
            const rows = status ? page.results.filter((o) => o.status === status) : page.results
            return rows.length === 0 ? (
              <div className="card-block"><EmptyState icon="cart" title={t('store.noOrders')} /></div>
            ) : (
              rows.map((order) => (
                <OrderCard key={order.id} order={order} seller>
                  <p className="text-caption">
                    {t('store.buyer')}: {order.buyer_name} · {name(order.delivery_governorate)} · {order.delivery_address}
                    {order.delivery_latitude && order.delivery_longitude ? (
                      <>
                        {' · '}
                        <a
                          href={`https://www.openstreetmap.org/?mlat=${order.delivery_latitude}&mlon=${order.delivery_longitude}#map=17/${order.delivery_latitude}/${order.delivery_longitude}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {t('store.deliveryPin')}
                        </a>
                      </>
                    ) : null}
                  </p>
                  <SellerActions order={order} company={company} onDone={() => { setError(null); reload() }} onError={(e) => setError(toErrorMessage(e))} />
                </OrderCard>
              ))
            )
          }}
        </AsyncPage>
      </PageStack>
    </Container>
  )
}

function SellerActions({ order, company, onDone, onError }: { order: Order; company?: string; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const [reference, setReference] = useState('')
  if (order.status === 'PLACED') {
    return (
      <div className="cluster">
        <ApiActionButton size="sm" action={() => commerce.moveOrder(order.id, 'CONFIRMED', company)} onSuccess={onDone} onError={onError} leading={<Icon name="check" size={14} />}>
          {t('market.accept')}
        </ApiActionButton>
        <ApiActionButton size="sm" variant="ghost" action={() => commerce.moveOrder(order.id, 'CANCELLED', company, { reason: t('market.declinedReason') })} onSuccess={onDone} onError={onError}>
          {t('market.decline')}
        </ApiActionButton>
      </div>
    )
  }
  if (order.status === 'CONFIRMED') {
    return (
      <div className="cluster" style={{ alignItems: 'flex-end' }}>
        <TextField label={t('market.shippingRef')} optional maxLength={120} value={reference} onChange={(e) => setReference(e.target.value)} />
        <ApiActionButton size="sm" action={() => commerce.moveOrder(order.id, 'SHIPPED', company, { shipping_reference: reference })} onSuccess={onDone} onError={onError} leading={<Icon name="box" size={14} />}>
          {t('market.ship')}
        </ApiActionButton>
        <ApiActionButton size="sm" variant="ghost" action={() => commerce.moveOrder(order.id, 'CANCELLED', company, { reason: t('market.declinedReason') })} onSuccess={onDone} onError={onError}>
          {t('market.decline')}
        </ApiActionButton>
      </div>
    )
  }
  if (order.status === 'SHIPPED') return <p className="text-caption">{t('market.waitingBuyer')}</p>
  if (order.status === 'DELIVERED') return <p className="text-caption">{t('market.waitingFinance')}</p>
  return null
}
