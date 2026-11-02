import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { workspaces as api } from '../../api'
import type { Order, OrderStatus } from '../../api'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Badge,
  Container,
  EmptyState,
  Icon,
  LinkButton,
  PageHeader,
  PageStack,
  SectionCard,
  type BadgeTone,
} from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import { pickScript, useLocalizedName } from '../../i18n/localized'
import { OrderTracker } from './OrderTracker'

const TONE: Record<OrderStatus, BadgeTone> = {
  PLACED: 'warning',
  CONFIRMED: 'brand',
  SHIPPED: 'brand',
  DELIVERED: 'success',
  CANCELLED: 'neutral',
}
const MERCHANT_NEXT: Partial<Record<OrderStatus, Exclude<OrderStatus, 'PLACED'>[]>> = {
  PLACED: ['CONFIRMED', 'CANCELLED'],
  CONFIRMED: ['SHIPPED', 'CANCELLED'],
  SHIPPED: ['DELIVERED'],
}

function OrderCard({ order, children }: { order: Order; children?: React.ReactNode }) {
  const { t, i18n } = useTranslation()
  return (
    <SectionCard
      title={<span className="ltr">{order.number}</span>}
      description={pickScript(order.merchant.name, i18n.language)}
      headingLevel={2}
      actions={<Badge tone={TONE[order.status]}>{t(`store.orderStatus.${order.status}`)}</Badge>}
    >
      <ul className="stack-sm" style={{ margin: 0, paddingInlineStart: '1.25rem' }}>
        {order.items.map((item) => (
          <li key={item.id}>
            {pickScript(item.title_snapshot, i18n.language)} × {item.quantity} —{' '}
            <span className="ltr">{Number(item.line_total).toLocaleString(i18n.language)} {order.currency}</span>
          </li>
        ))}
      </ul>
      <div className="cluster text-caption">
        <strong className="ltr">{Number(order.total).toLocaleString(i18n.language)} {order.currency}</strong>
        <span>{t(`store.paymentMethods.${order.payment_method}`)}</span>
        <Badge tone={order.payment_status === 'PAID' ? 'success' : 'neutral'}>{t(`store.paymentStatus.${order.payment_status}`)}</Badge>
        <time dateTime={order.created_at}>{new Date(order.created_at).toLocaleString(i18n.language)}</time>
      </div>
      <OrderTracker status={order.status} />
      {children}
    </SectionCard>
  )
}

/** /orders — the buyer's own store orders (server-scoped to the caller). */
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
        <Alert kind="info">{t('store.demoPayment')}</Alert>
        {error ? <Alert kind="error">{error}</Alert> : null}
        <AsyncPage load={(signal) => api.listMyOrders(1, signal)}>
          {(page, reload) =>
            page.results.length === 0 ? (
              <div className="card-block"><EmptyState icon="cart" title={t('store.noOrders')} /></div>
            ) : (
              page.results.map((order) => (
                <OrderCard key={order.id} order={order}>
                  {order.status === 'PLACED' || order.status === 'CONFIRMED' ? (
                    <ApiActionButton
                      size="sm"
                      variant="ghost"
                      action={() => api.cancelMyOrder(order.id)}
                      onSuccess={reload}
                      onError={(e) => setError(toErrorMessage(e))}
                    >
                      {t('store.cancelOrder')}
                    </ApiActionButton>
                  ) : null}
                </OrderCard>
              ))
            )
          }
        </AsyncPage>
      </PageStack>
    </Container>
  )
}

/** /merchant/orders[?company=] — orders of a business the caller owns or works for. */
export function MerchantOrdersPage() {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const [params] = useSearchParams()
  const company = params.get('company') ?? undefined
  const [error, setError] = useState<string | null>(null)
  return (
    <Container width="xl">
      <PageHeader eyebrow={<><Icon name="cart" size={16} />{t('nav.store')}</>} title={t('store.merchantOrders')} />
      <PageStack>
        <Alert kind="info">{t('store.demoPayment')}</Alert>
        {error ? <Alert kind="error">{error}</Alert> : null}
        <AsyncPage load={(signal) => api.listMerchantOrders(company, 1, signal)} deps={[company]}>
          {(page, reload) =>
            page.results.length === 0 ? (
              <div className="card-block"><EmptyState icon="cart" title={t('store.noOrders')} /></div>
            ) : (
              page.results.map((order) => (
                <OrderCard key={order.id} order={order}>
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
                  <div className="cluster">
                    {(MERCHANT_NEXT[order.status] ?? []).map((next) => (
                      <ApiActionButton
                        key={next}
                        size="sm"
                        variant={next === 'CANCELLED' ? 'ghost' : 'primary'}
                        action={() => api.moveMerchantOrder(order.id, next, company)}
                        onSuccess={() => { setError(null); reload() }}
                        onError={(e) => setError(toErrorMessage(e))}
                      >
                        {t(`store.advance.${next}`)}
                      </ApiActionButton>
                    ))}
                    {order.payment_method === 'MANUAL_TRANSFER' && order.payment_status === 'UNPAID' && order.status !== 'CANCELLED' ? (
                      <ApiActionButton
                        size="sm"
                        variant="secondary"
                        action={() => api.recordOrderPayment(order.id, company)}
                        onSuccess={reload}
                        onError={(e) => setError(toErrorMessage(e))}
                      >
                        {t('store.markPaid')}
                      </ApiActionButton>
                    ) : null}
                  </div>
                </OrderCard>
              ))
            )
          }
        </AsyncPage>
      </PageStack>
    </Container>
  )
}
