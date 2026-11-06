import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { ApiError, commerce, reference, workspaces as api } from '../../api'
import type { CheckoutResult, DeliveryDefaults, Governorate, StorePaymentMethod, StoreProduct } from '../../api'
import { useAuth } from '../../auth/useAuth'
import { cart, useCart, type CartLine } from '../../cart/cart'
import { nearestGovernorateSlug } from '../../cart/governorates'
import {
  Alert,
  AsyncPage,
  Badge,
  Button,
  Container,
  EmptyState,
  FormActions,
  Icon,
  LinkButton,
  PageHeader,
  PhoneField,
  ProductImage,
  Select,
  TextField,
  Textarea,
} from '../../design-system'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'
import { pickScript, useLocalizedName } from '../../i18n/localized'
import { normalizeIraqiPhone } from '../validation'
import { newIdempotencyKey, useMoney } from '../market/money'
import { MoneyTable } from '../market/MoneyTable'
import styles from './cart.module.css'
import { OrderTracker } from './OrderTracker'
import { QuantityStepper } from './StoreParts'
import { formatPrice } from './storeActions'

type Availability = { state: 'ok' | 'few' | 'out' | 'gone'; price?: string }

/**
 * /cart — "My cart": what the visitor chose (kept in this browser), the CURRENT status of each item
 * re-read from the store (available / few left / out of stock / no longer sold / price changed),
 * one checkout per store, and — when signed in — the progress of recent orders. Only product ids and
 * quantities are sent at checkout; the server re-reads every price and stock figure.
 */
export function CartPage() {
  const { t, i18n } = useTranslation()
  const { account } = useAuth()
  const lines = useCart()
  const [placed, setPlaced] = useState<CheckoutResult | null>(null)
  const ids = lines.map((line) => line.product).sort().join(',')
  const live = useAsyncData(
    async (signal) => {
      const entries = await Promise.all(
        lines.map(async (line): Promise<[string, Availability]> => {
          try {
            const p: StoreProduct = await api.getStoreProduct(line.product, signal)
            return [line.product, { state: !p.in_stock ? 'out' : p.low_stock ? 'few' : 'ok', price: p.price }]
          } catch (error) {
            if (error instanceof ApiError && error.status === 404) return [line.product, { state: 'gone' }]
            throw error
          }
        }),
      )
      return Object.fromEntries(entries) as Record<string, Availability>
    },
    [ids],
  )
  const byMerchant = new Map<string, CartLine[]>()
  for (const line of lines) byMerchant.set(line.merchantId, [...(byMerchant.get(line.merchantId) ?? []), line])
  const units = lines.reduce((n, l) => n + l.quantity, 0)

  return (
    <Container width="xl">
      <PageHeader
        eyebrow={<><Icon name="cart" size={16} />{t('nav.store')}</>}
        title={t('nav.myCart')}
        description={units > 0 ? t('store.cartSummary', { count: units }) : t('market.cartIntro')}
        actions={<LinkButton to="/store" variant="secondary" leading={<Icon name="search" size={16} />}>{t('store.continueShopping')}</LinkButton>}
      />
      {placed ? (
        <Alert kind="success">
          <span data-testid="checkout-placed">
            {t('market.placed', { number: placed.number, count: placed.orders.length })}{' '}
            {placed.orders.map((o) => o.number).join(' · ')}{' '}
          </span>
          <Link to="/orders">{t('store.myOrders')}</Link>
        </Alert>
      ) : null}
      {lines.length === 0 ? (
        <div className="card-block">
          <EmptyState icon="cart" title={t('store.cartEmpty')} action={<LinkButton to="/store">{t('nav.store')}</LinkButton>}>
            {t('store.cartEmptyHint')}
          </EmptyState>
        </div>
      ) : (
        <div className={styles.layout}>
          <div className="stack-lg">
            {[...byMerchant.entries()].map(([merchantId, group]) => (
              <section key={merchantId} className={styles.panel} aria-label={pickScript(group[0]!.merchantName, i18n.language)}>
                <h2 className={styles.panelTitle}>
                  <Icon name="building" size={18} /> {t('store.fromStore', { name: pickScript(group[0]!.merchantName, i18n.language) })}
                </h2>
                <ul className={styles.lines} data-testid="cart-lines">
                  {group.map((line) => (
                    <CartRow key={line.product} line={line} availability={live.data?.[line.product]} />
                  ))}
                </ul>
              </section>
            ))}
          </div>
          <CheckoutPanel
            lines={lines}
            blocked={lines.some((l) => ['out', 'gone'].includes(live.data?.[l.product]?.state ?? 'ok'))}
            signedIn={Boolean(account)}
            onPlaced={(result) => {
              cart.clear()
              setPlaced(result)
            }}
          />
        </div>
      )}
      {account ? <RecentOrders /> : null}
    </Container>
  )
}

function CartRow({ line, availability }: { line: CartLine; availability: Availability | undefined }) {
  const { t, i18n } = useTranslation()
  const title = pickScript(line.title, i18n.language)
  const changed = availability?.price !== undefined && Number(availability.price) !== Number(line.price)
  return (
    <li className={styles.line} data-testid="cart-line">
      <ProductImage src={line.image} alt={title} size="sm" />
      <div className={styles.lineBody}>
        <Link to={`/store/${line.product}`} className={styles.lineTitle}>
          {title}
        </Link>
        <span className={`${styles.lineMeta} ltr`}>
          {formatPrice(line.price, line.currency, i18n.language)} × {line.quantity}
        </span>
        <div>
          {availability === undefined ? (
            <Badge tone="neutral">{t('store.checking')}</Badge>
          ) : availability.state === 'gone' ? (
            <Badge tone="error">{t('store.noLongerSold')}</Badge>
          ) : availability.state === 'out' ? (
            <Badge tone="error">{t('store.outOfStock')}</Badge>
          ) : availability.state === 'few' ? (
            <Badge tone="warning">{t('store.fewLeft')}</Badge>
          ) : (
            <Badge tone="success">{t('store.available')}</Badge>
          )}{' '}
          {changed ? (
            <Badge tone="warning">
              {t('store.priceChanged', { price: formatPrice(availability!.price!, line.currency, i18n.language) })}
            </Badge>
          ) : null}
        </div>
        <div className={styles.lineFoot}>
          <QuantityStepper value={line.quantity} onChange={(next) => cart.setQuantity(line.product, next)} />
          <span className={`${styles.lineTotal} ltr`}>{formatPrice(Number(line.price) * line.quantity, line.currency, i18n.language)}</span>
          <button type="button" className={styles.remove} onClick={() => cart.remove(line.product)}>
            <Icon name="trash" size={14} /> {t('store.remove')}
          </button>
        </div>
      </div>
    </li>
  )
}

/**
 * ONE checkout for the whole cart: the server splits it into one order per seller, applies sales
 * and coupons, and returns the exact amounts shown here (nothing is computed in the browser).
 */
function CheckoutPanel({
  lines,
  blocked,
  signedIn,
  onPlaced,
}: {
  lines: CartLine[]
  blocked: boolean
  signedIn: boolean
  onPlaced: (result: CheckoutResult) => void
}) {
  const { t, i18n } = useTranslation()
  const money = useMoney()
  const [codes, setCodes] = useState<string[]>([])
  const [codeInput, setCodeInput] = useState('')
  const signature = lines.map((l) => `${l.product}:${l.quantity}`).sort().join(',')
  const preview = useAsyncData(
    (signal) =>
      signedIn
        ? commerce.previewCheckout(lines.map((l) => ({ product: l.product, quantity: l.quantity })), codes, signal)
        : Promise.resolve(null),
    [signature, codes.join(','), signedIn],
  )
  const estimate = lines.reduce((sum, l) => sum + Number(l.price) * l.quantity, 0)
  const data = preview.data
  const addCode = (event: FormEvent) => {
    event.preventDefault()
    const code = codeInput.trim().toUpperCase()
    if (code && !codes.includes(code)) setCodes([...codes, code])
    setCodeInput('')
  }
  return (
    <aside className={styles.panel} aria-label={t('store.checkout')} data-testid="checkout-panel">
      <h2 className={styles.panelTitle}>{t('store.orderSummary')}</h2>
      {data ? (
        <div className="stack-sm" data-testid="checkout-preview">
          {data.orders.map((order) => (
            <div key={order.merchant.id} className="stack-xs">
              <strong className="text-caption">
                <Icon name="building" size={14} /> {pickScript(order.merchant.name, i18n.language)}
              </strong>
              <MoneyTable
                rows={[
                  { label: t('market.listTotal'), value: order.list_total },
                  { label: t('market.sellerDiscount') + (order.seller_coupon ? ` (${order.seller_coupon})` : ''), value: order.seller_discount_total, minus: true, hidden: Number(order.seller_discount_total) === 0 },
                  { label: t('market.racheetaDiscount'), value: order.platform_discount_total, minus: true, hidden: Number(order.platform_discount_total) === 0 },
                  { label: t('market.orderTotal'), value: order.total, strong: true },
                ]}
              />
            </div>
          ))}
          <div className={styles.summaryRow}>
            <span>{t('market.toPay', { count: data.orders.length })}</span>
            <span className={`${styles.summaryTotal} ltr`} data-testid="checkout-total">{money(data.total)}</span>
          </div>
        </div>
      ) : (
        <div className={styles.summaryRow}>
          <span>{t('store.total')}</span>
          <span className={`${styles.summaryTotal} ltr`}>{formatPrice(estimate, lines[0]?.currency ?? 'IQD', i18n.language)}</span>
        </div>
      )}
      {preview.error ? <Alert kind="error">{toErrorMessage(preview.error)}</Alert> : null}
      {signedIn ? (
        <form onSubmit={addCode} className="cluster" aria-label={t('market.coupon')}>
          <TextField
            label={t('market.coupon')}
            optional
            value={codeInput}
            maxLength={32}
            onChange={(e) => setCodeInput(e.target.value)}
            hint={t('market.couponHint')}
          />
          <Button type="submit" size="sm" variant="secondary" disabled={!codeInput.trim()}>
            {t('market.applyCoupon')}
          </Button>
        </form>
      ) : null}
      {codes.length ? (
        <div className="cluster" data-testid="applied-coupons">
          {codes.map((code) => (
            <Badge key={code} tone="brand">
              <span className="ltr">{code}</span>{' '}
              <button type="button" className={styles.remove} aria-label={t('market.removeCoupon', { code })} onClick={() => setCodes(codes.filter((c) => c !== code))}>
                <Icon name="x" size={12} />
              </button>
            </Badge>
          ))}
        </div>
      ) : null}
      <p className="text-caption">{t('market.serverPriced')}</p>
      <p className="text-caption">
        <Icon name="info" size={14} /> {t('store.demoPayment')}
      </p>
      {blocked ? <Alert kind="warning">{t('store.fixCart')}</Alert> : null}
      {!signedIn ? (
        <Alert kind="info">
          {t('store.loginToOrder')} <Link to="/login" state={{ from: '/cart' }}>{t('nav.login')}</Link>
        </Alert>
      ) : (
        <AsyncPage
          load={async (signal) => {
            const [defaults, governorates] = await Promise.all([
              api.getDeliveryDefaults(signal),
              reference.listGovernorates(undefined, signal),
            ])
            return { defaults, governorates }
          }}
        >
          {({ defaults, governorates }) => (
            <CheckoutForm
              lines={lines}
              coupons={codes}
              blocked={blocked || Boolean(preview.error)}
              defaults={defaults}
              governorates={governorates}
              onPlaced={onPlaced}
            />
          )}
        </AsyncPage>
      )}
    </aside>
  )
}

type Pin = { latitude: string; longitude: string } | null

function CheckoutForm({
  lines,
  coupons,
  blocked,
  defaults,
  governorates,
  onPlaced,
}: {
  lines: CartLine[]
  coupons: string[]
  blocked: boolean
  defaults: DeliveryDefaults
  governorates: Governorate[]
  onPlaced: (result: CheckoutResult) => void
}) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  // Pre-filled from the buyer's last delivery (or account phone); every field stays editable.
  const [governorate, setGovernorate] = useState(defaults.governorate ?? '')
  const [address, setAddress] = useState(defaults.address)
  const [phone, setPhone] = useState(defaults.phone)
  const [note, setNote] = useState('')
  const [method, setMethod] = useState<StorePaymentMethod>('CASH_ON_DELIVERY')
  const [pin, setPin] = useState<Pin>(null)
  const [locating, setLocating] = useState(false)
  const [locationMessage, setLocationMessage] = useState<string | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // One key per attempt: a retried or double-clicked submit returns the same checkout. A changed
  // cart starts a new attempt.
  const attempt = useRef<string | null>(null)
  const signature = `${lines.map((l) => `${l.product}:${l.quantity}`).join(',')}|${coupons.join(',')}`
  useEffect(() => {
    attempt.current = null
  }, [signature])

  const useMyLocation = () => {
    if (!('geolocation' in navigator)) {
      setLocationMessage(t('location.unsupported'))
      return
    }
    setLocating(true)
    setLocationMessage(null)
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false)
        const latitude = position.coords.latitude
        const longitude = position.coords.longitude
        setPin({ latitude: latitude.toFixed(6), longitude: longitude.toFixed(6) })
        const slug = nearestGovernorateSlug(latitude, longitude, governorates.map((g) => g.slug))
        const match = governorates.find((g) => g.slug === slug)
        if (match) setGovernorate(match.id)
      },
      (failure) => {
        setLocating(false)
        setLocationMessage(failure.code === failure.PERMISSION_DENIED ? t('location.denied') : t('location.unavailable'))
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    )
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const next: Record<string, string> = {}
    if (!governorate) next.governorate = t('validation.required')
    if (address.trim().length < 5) next.address = t('store.addressHint')
    const normalized = normalizeIraqiPhone(phone, { mobileOnly: true })
    if (!normalized) next.phone = t('validation.mobile')
    setErrors(next)
    if (Object.keys(next).length) return
    setBusy(true)
    setError(null)
    try {
      attempt.current ??= newIdempotencyKey()
      const result = await commerce.placeCheckout({
        idempotency_key: attempt.current,
        coupons,
        items: lines.map((l) => ({ product: l.product, quantity: l.quantity })),
        payment_method: method,
        governorate,
        address: address.trim(),
        phone: normalized!,
        note: note.trim(),
        ...(pin ? { latitude: pin.latitude, longitude: pin.longitude } : {}),
      })
      attempt.current = null
      onPlaced(result)
    } catch (e) {
      setError(toErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} noValidate className="stack-sm" data-testid="checkout-form">
      {error ? <Alert kind="error">{error}</Alert> : null}
      {defaults.address ? <p className="text-caption">{t('store.prefilled')}</p> : null}
      <div className={styles.locate}>
        <Button type="button" size="sm" variant="secondary" onClick={useMyLocation} loading={locating} loadingLabel={t('location.locating')} leading={<Icon name="mapPin" size={16} />}>
          {pin ? t('location.update') : t('location.useMine')}
        </Button>
        {pin ? (
          <span className={styles.pin} data-testid="delivery-pin">
            <Icon name="check" size={14} /> {t('store.pinAttached')}{' '}
            <a href={`https://www.openstreetmap.org/?mlat=${pin.latitude}&mlon=${pin.longitude}#map=17/${pin.latitude}/${pin.longitude}`} target="_blank" rel="noopener noreferrer">
              {t('location.viewMap')}
            </a>{' '}
            <button type="button" className={styles.remove} onClick={() => setPin(null)}>
              {t('location.clear')}
            </button>
          </span>
        ) : null}
      </div>
      {locationMessage ? <Alert kind="warning">{locationMessage}</Alert> : null}
      <Select label={t('store.governorate')} required value={governorate} onChange={(e) => setGovernorate(e.target.value)} error={errors.governorate}>
        <option value="">{t('store.chooseGovernorate')}</option>
        {governorates.map((g) => (
          <option key={g.id} value={g.id}>{name(g)}</option>
        ))}
      </Select>
      <TextField label={t('store.address')} required maxLength={255} value={address} onChange={(e) => setAddress(e.target.value)} error={errors.address} />
      <PhoneField label={t('store.phone')} required hint={t('validation.mobileHint')} value={phone} onChange={(e) => setPhone(e.target.value)} error={errors.phone} />
      <Select label={t('store.payment')} value={method} onChange={(e) => setMethod(e.target.value as StorePaymentMethod)}>
        <option value="CASH_ON_DELIVERY">{t('store.paymentMethods.CASH_ON_DELIVERY')}</option>
        <option value="MANUAL_TRANSFER">{t('store.paymentMethods.MANUAL_TRANSFER')}</option>
      </Select>
      <Textarea label={t('store.note')} optional maxLength={500} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
      <FormActions>
        <Button type="submit" loading={busy} loadingLabel={t('store.placing')} disabled={blocked} leading={<Icon name="check" size={16} />}>
          {t('store.checkout')}
        </Button>
      </FormActions>
    </form>
  )
}

/** The status of what this person already ordered (latest three), with a progress tracker. */
function RecentOrders() {
  const { t, i18n } = useTranslation()
  const orders = useAsyncData((signal) => api.listMyOrders(1, signal), [])
  const rows = (orders.data?.results ?? []).slice(0, 3)
  if (orders.loading || orders.error || rows.length === 0) return null
  return (
    <section className={styles.panel} style={{ marginTop: 'var(--space-6)' }} data-testid="recent-orders">
      <div className={styles.orderHead}>
        <h2 className={styles.panelTitle}>{t('store.recentOrders')}</h2>
        <LinkButton to="/orders" size="sm" variant="ghost">{t('store.allOrders')}</LinkButton>
      </div>
      <ul className={styles.orders}>
        {rows.map((order) => (
          <li key={order.id} className="stack-sm">
            <div className={styles.orderHead}>
              <strong className="ltr">{order.number}</strong>
              <span className="text-caption">
                {pickScript(order.merchant.name, i18n.language)} · <span className="ltr">{formatPrice(order.total, order.currency, i18n.language)}</span>
              </span>
            </div>
            <OrderTracker status={order.status} />
          </li>
        ))}
      </ul>
    </section>
  )
}
