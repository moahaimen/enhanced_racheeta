import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { reference, workspaces as api } from '../../api'
import type { Order, StorePaymentMethod } from '../../api'
import { useAuth } from '../../auth/useAuth'
import {
  Alert,
  AsyncPage,
  Button,
  Container,
  EmptyState,
  FormActions,
  Icon,
  LinkButton,
  PageHeader,
  PageStack,
  SectionCard,
  Select,
  TextField,
  PhoneField,
  Textarea,
} from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import { pickScript, useLocalizedName } from '../../i18n/localized'
import { normalizeIraqiPhone } from '../validation'
import { cart, useCart, type CartLine } from './cart'

/** /cart — one checkout per store. Only ids and quantities are sent; the server prices the order. */
export function CartPage() {
  const { t } = useTranslation()
  const lines = useCart()
  const [placed, setPlaced] = useState<Order | null>(null)
  const byMerchant = new Map<string, CartLine[]>()
  for (const line of lines) byMerchant.set(line.merchantId, [...(byMerchant.get(line.merchantId) ?? []), line])
  return (
    <Container width="lg">
      <PageHeader eyebrow={<><Icon name="cart" size={16} />{t('nav.store')}</>} title={t('store.cartTitle')} description={t('store.oneStore')} />
      <PageStack>
        <Alert kind="info">{t('store.demoPayment')}</Alert>
        {placed ? (
          <Alert kind="success">
            {t('store.placed', { number: placed.number })} <Link to="/orders">{t('store.myOrders')}</Link>
          </Alert>
        ) : null}
        {lines.length === 0 ? (
          <div className="card-block">
            <EmptyState icon="cart" title={t('store.cartEmpty')} action={<LinkButton to="/store">{t('nav.store')}</LinkButton>} />
          </div>
        ) : (
          [...byMerchant.entries()].map(([merchantId, group]) => (
            <MerchantCheckout key={merchantId} lines={group} onPlaced={(order) => { cart.removeMerchant(merchantId); setPlaced(order) }} />
          ))
        )}
      </PageStack>
    </Container>
  )
}

function MerchantCheckout({ lines, onPlaced }: { lines: CartLine[]; onPlaced: (order: Order) => void }) {
  const { t, i18n } = useTranslation()
  const { account } = useAuth()
  const name = useLocalizedName()
  const [governorate, setGovernorate] = useState('')
  const [address, setAddress] = useState('')
  const [phone, setPhone] = useState('')
  const [note, setNote] = useState('')
  const [method, setMethod] = useState<StorePaymentMethod>('CASH_ON_DELIVERY')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const estimate = lines.reduce((sum, l) => sum + Number(l.price) * l.quantity, 0)

  const [phoneError, setPhoneError] = useState<string | null>(null)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const normalized = normalizeIraqiPhone(phone, { mobileOnly: true })
    if (!normalized) {
      setPhoneError(t('validation.mobile'))
      return
    }
    setPhoneError(null)
    setBusy(true)
    setError(null)
    try {
      const order = await api.placeOrder({
        items: lines.map((l) => ({ product: l.product, quantity: l.quantity })),
        payment_method: method,
        governorate,
        address,
        phone: normalized,
        note,
      })
      onPlaced(order)
    } catch (e) {
      setError(toErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard title={pickScript(lines[0]!.merchantName, i18n.language)} headingLevel={2}>
      <ul className="stack-sm" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {lines.map((line) => (
          <li key={line.product} className="cluster">
            <span>{pickScript(line.title, i18n.language)}</span>
            <TextField
              label={t('store.quantity')}
              type="number"
              min={1}
              max={20}
              value={line.quantity}
              onChange={(e) => cart.setQuantity(line.product, Number(e.target.value) || 1)}
            />
            <span className="ltr">{(Number(line.price) * line.quantity).toLocaleString(i18n.language)} {line.currency}</span>
            <Button size="sm" variant="ghost" onClick={() => cart.remove(line.product)}>{t('store.remove')}</Button>
          </li>
        ))}
      </ul>
      <p>
        <strong>{t('store.total')}: </strong>
        <span className="ltr">{estimate.toLocaleString(i18n.language)} {lines[0]!.currency}</span>
        <br />
        <span className="text-caption">{t('store.serverTotal')}</span>
      </p>
      {!account ? (
        <Alert kind="info">
          {t('store.loginToOrder')} <Link to="/login?next=/cart">{t('nav.login')}</Link>
        </Alert>
      ) : (
        <form onSubmit={submit} className="stack-sm" data-testid="checkout-form">
          {error ? <Alert kind="error">{error}</Alert> : null}
          <AsyncPage load={(signal) => reference.listGovernorates(undefined, signal)}>
            {(governorates) => (
              <Select label={t('store.governorate')} required value={governorate} onChange={(e) => setGovernorate(e.target.value)}>
                <option value="" />
                {governorates.map((g) => <option key={g.id} value={g.id}>{name(g)}</option>)}
              </Select>
            )}
          </AsyncPage>
          <TextField label={t('store.address')} required maxLength={255} value={address} onChange={(e) => setAddress(e.target.value)} />
          <PhoneField label={t('store.phone')} required hint={t('validation.mobileHint')} value={phone} onChange={(e) => setPhone(e.target.value)} error={phoneError ?? undefined} />
          <Select label={t('store.payment')} value={method} onChange={(e) => setMethod(e.target.value as StorePaymentMethod)}>
            <option value="CASH_ON_DELIVERY">{t('store.paymentMethods.CASH_ON_DELIVERY')}</option>
            <option value="MANUAL_TRANSFER">{t('store.paymentMethods.MANUAL_TRANSFER')}</option>
          </Select>
          <Textarea label={t('store.note')} optional maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
          <FormActions>
            <Button type="submit" loading={busy} loadingLabel={t('store.placing')}>{t('store.checkout')}</Button>
          </FormActions>
        </form>
      )}
    </SectionCard>
  )
}
