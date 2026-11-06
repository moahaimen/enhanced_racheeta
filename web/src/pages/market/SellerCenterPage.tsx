import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { commerce } from '../../api'
import type { CouponInput, DiscountKind, InventoryRow } from '../../api'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Badge,
  Button,
  Container,
  EmptyState,
  Icon,
  PageHeader,
  PageStack,
  ProductImage,
  SectionCard,
  Select,
  StatCard,
  TextField,
} from '../../design-system'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'
import { pickScript } from '../../i18n/localized'
import { RETURN_TONE } from './tones'
import { useMoney } from './money'
import { SellerNav } from './SellerNav'
import { CatalogTab, DeliveryTab, ReportsTab, SetupTab } from './SellerSetupTabs'

const TABS = ['setup', 'catalog', 'delivery', 'returns', 'inventory', 'promotions', 'finance', 'reports'] as const
type Tab = (typeof TABS)[number]

/**
 * /merchant/center?tab=…[&company=] — the seller's own operations: returns, stock, coupons and
 * sales, and the merchant statement. Every action is re-authorized by the server for THIS business
 * and the caller's staff role (owner, manager, product editor, stock manager, fulfillment, finance).
 */
export function SellerCenterPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const raw = params.get('tab')
  const tab: Tab = TABS.includes(raw as Tab) ? (raw as Tab) : 'inventory'
  const company = params.get('company') ?? undefined
  return (
    <Container width="xl">
      <PageHeader eyebrow={<><Icon name="building" size={16} />{t('market.sellerCenter')}</>} title={t(`market.nav.${tab}`)} description={t(`market.intro.${tab}`)} />
      <SellerNav active={tab} />
      <PageStack>
        {tab === 'returns' ? (
          <ReturnsTab company={company} />
        ) : tab === 'promotions' ? (
          <PromotionsTab company={company} />
        ) : tab === 'finance' ? (
          <FinanceTab company={company} />
        ) : tab === 'setup' ? (
          <SetupTab company={company} />
        ) : tab === 'catalog' ? (
          <CatalogTab company={company} />
        ) : tab === 'delivery' ? (
          <DeliveryTab company={company} />
        ) : tab === 'reports' ? (
          <ReportsTab company={company} />
        ) : (
          <InventoryTab company={company} />
        )}
      </PageStack>
    </Container>
  )
}

function useErrors() {
  const [error, setError] = useState<string | null>(null)
  return { error, fail: (e: unknown) => setError(toErrorMessage(e)), clear: () => setError(null) }
}

// ---- returns ----------------------------------------------------------------------------------------
function ReturnsTab({ company }: { company?: string }) {
  const { t, i18n } = useTranslation()
  const { error, fail, clear } = useErrors()
  return (
    <>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <AsyncPage load={(signal) => commerce.listSellerReturns(company, signal)} deps={[company]}>
        {(page, reload) =>
          page.results.length === 0 ? (
            <div className="card-block"><EmptyState icon="refresh" title={t('market.noReturns')} /></div>
          ) : (
            page.results.map((r) => (
              <SectionCard
                key={r.id}
                headingLevel={2}
                title={<span className="ltr">{r.order.number}</span>}
                actions={<Badge tone={RETURN_TONE[r.status]}>{t(`market.returnStatus.${r.status}`)}</Badge>}
              >
                <p>{r.lines.map((l) => `${pickScript(l.title, i18n.language)} × ${l.quantity}`).join(', ')}</p>
                <p className="text-caption">{t('market.reason')}: {r.reason}</p>
                <div className="cluster">
                  {r.status === 'REQUESTED' ? (
                    <>
                      <ApiActionButton size="sm" action={() => commerce.decideReturn(r.id, true, company)} onSuccess={() => { clear(); reload() }} onError={fail}>
                        {t('market.approveReturn')}
                      </ApiActionButton>
                      <ApiActionButton size="sm" variant="ghost" action={() => commerce.decideReturn(r.id, false, company, t('market.rejectedNote'))} onSuccess={() => { clear(); reload() }} onError={fail}>
                        {t('market.rejectReturn')}
                      </ApiActionButton>
                    </>
                  ) : null}
                  {r.status === 'APPROVED' ? (
                    <ApiActionButton size="sm" action={() => commerce.receiveReturn(r.id, company)} onSuccess={() => { clear(); reload() }} onError={fail} leading={<Icon name="box" size={14} />}>
                      {t('market.markReceived')}
                    </ApiActionButton>
                  ) : null}
                  {r.status === 'RECEIVED' ? <p className="text-caption">{t('market.waitingRefund')}</p> : null}
                </div>
              </SectionCard>
            ))
          )
        }
      </AsyncPage>
    </>
  )
}

// ---- inventory --------------------------------------------------------------------------------------
function InventoryTab({ company }: { company?: string }) {
  const { t, i18n } = useTranslation()
  const money = useMoney()
  const { error, fail, clear } = useErrors()
  const [open, setOpen] = useState<string | null>(null)
  return (
    <>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <AsyncPage load={(signal) => commerce.listInventory(company, signal)} deps={[company]}>
        {(rows, reload) => (
          <div className="card-block table-scroll">
            <table className="data-table" data-testid="inventory-table">
              <thead>
                <tr>
                  <th scope="col">{t('market.product')}</th>
                  <th scope="col" className="num">{t('market.price')}</th>
                  <th scope="col" className="num">{t('market.onHand')}</th>
                  <th scope="col" className="num">{t('market.reserved')}</th>
                  <th scope="col" className="num">{t('market.available')}</th>
                  <th scope="col" className="num">{t('market.alertLevel')}</th>
                  <th scope="col"><span className="visually-hidden">{t('market.actions')}</span></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <InventoryLine
                    key={unitKey(row)}
                    row={row}
                    open={open === unitKey(row)}
                    onToggle={() => setOpen(open === unitKey(row) ? null : unitKey(row))}
                    company={company}
                    onSaved={() => { clear(); reload() }}
                    onError={fail}
                    title={pickScript(row.title, i18n.language)}
                    price={row.price ? money(row.price) : '—'}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </AsyncPage>
    </>
  )
}

/** One stock unit: a product without options, or one option (variant) of a product. */
function unitKey(row: InventoryRow): string {
  return row.variant_id ? `${row.id}:${row.variant_id}` : row.id
}

function InventoryLine({ row, open, onToggle, company, onSaved, onError, title, price }: {
  row: InventoryRow
  open: boolean
  onToggle: () => void
  company?: string
  onSaved: () => void
  onError: (e: unknown) => void
  title: string
  price: string
}) {
  const { t, i18n } = useTranslation()
  const [delta, setDelta] = useState('')
  const [reason, setReason] = useState('')
  const [level, setLevel] = useState(row.reorder_threshold === null ? '' : String(row.reorder_threshold))
  const movements = useAsyncData((signal) => (open ? commerce.listMovements(row.id, company, signal) : Promise.resolve(null)), [open, row.on_hand, row.reserved])
  const tracked = row.on_hand !== null
  const adjust = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await commerce.adjustStock(row.id, Number(delta), reason.trim(), company, row.variant_id)
      setDelta('')
      setReason('')
      onSaved()
    } catch (e) {
      onError(e)
    }
  }
  return (
    <>
      <tr data-testid="inventory-row">
        <td>
          <span className="cluster"><ProductImage src={row.image_url} alt="" size="sm" /> {title}</span>
          {row.variant_label ? <span className="text-caption" data-testid="inventory-variant"> · {row.variant_label}</span> : null}
          {row.sku ? <div className="text-caption ltr">{row.sku}</div> : null}
          {row.low ? <Badge tone="warning">{t('market.lowStock')}</Badge> : null} {!row.is_active ? <Badge tone="neutral">{t('market.inactive')}</Badge> : null}
        </td>
        <td className="num ltr">{price}</td>
        <td className="num">{tracked ? row.on_hand : t('market.untracked')}</td>
        <td className="num">{row.reserved}</td>
        <td className="num"><strong>{tracked ? row.available : '—'}</strong></td>
        <td className="num">{row.reorder_threshold ?? '—'}</td>
        <td>
          <Button size="sm" variant="ghost" onClick={onToggle} aria-expanded={open}>{open ? t('market.close') : t('market.manage')}</Button>
        </td>
      </tr>
      {open ? (
        <tr>
          <td colSpan={7}>
            <div className="stack-sm">
              <form onSubmit={adjust} className="cluster" style={{ alignItems: 'flex-end' }} noValidate data-testid="adjust-form">
                <TextField label={t('market.adjustBy')} type="number" inputMode="numeric" value={delta} onChange={(e) => setDelta(e.target.value)} hint={t('market.adjustHint')} />
                <TextField label={t('market.reason')} maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)} />
                <Button type="submit" size="sm" disabled={!Number.isInteger(Number(delta)) || Number(delta) === 0 || !reason.trim()}>{t('market.saveStock')}</Button>
              </form>
              <div className="cluster" style={{ alignItems: 'flex-end' }}>
                <TextField label={t('market.alertLevel')} type="number" min={0} inputMode="numeric" value={level} onChange={(e) => setLevel(e.target.value)} />
                <ApiActionButton size="sm" variant="secondary" action={() => commerce.setReorderLevel(row.id, level === '' ? null : Number(level), company, row.variant_id)} onSuccess={onSaved} onError={onError}>
                  {t('market.saveAlert')}
                </ApiActionButton>
              </div>
              {movements.data ? (
                <table className="data-table" aria-label={t('market.movements')}>
                  <thead>
                    <tr>
                      <th scope="col">{t('market.when')}</th>
                      <th scope="col">{t('market.movement')}</th>
                      <th scope="col" className="num">{t('market.qty')}</th>
                      <th scope="col" className="num">{t('market.onHand')}</th>
                      <th scope="col" className="num">{t('market.reserved')}</th>
                      <th scope="col">{t('market.reason')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {movements.data.results.filter((m) => (m.variant_id ?? null) === (row.variant_id ?? null)).map((m) => (
                      <tr key={m.id}>
                        <td>{new Date(m.created_at).toLocaleString(i18n.language)}</td>
                        <td>{t(`market.movementKind.${m.kind}`)} {m.order_number ? <span className="ltr text-caption">{m.order_number}</span> : null}</td>
                        <td className="num ltr">{m.quantity > 0 ? `+${m.quantity}` : m.quantity}</td>
                        <td className="num">{m.on_hand_after}</td>
                        <td className="num">{m.reserved_after}</td>
                        <td>{m.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}
            </div>
          </td>
        </tr>
      ) : null}
    </>
  )
}

// ---- coupons and sales ------------------------------------------------------------------------------
function inDays(days: number): string {
  return new Date(Date.now() + days * 86400000).toISOString()
}

export function CouponForm({ onCreate, onError }: { onCreate: (input: CouponInput) => Promise<unknown>; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const [code, setCode] = useState('')
  const [kind, setKind] = useState<DiscountKind>('PERCENT')
  const [value, setValue] = useState('')
  const [minimum, setMinimum] = useState('')
  const [days, setDays] = useState('30')
  const [uses, setUses] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    try {
      await onCreate({
        code: code.trim().toUpperCase(),
        kind,
        value,
        min_subtotal: minimum || '0',
        ends_at: inDays(Number(days) || 30),
        max_redemptions: uses ? Number(uses) : null,
      })
      setCode('')
      setValue('')
    } catch (e) {
      onError(e)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form onSubmit={submit} className="cluster" style={{ alignItems: 'flex-end' }} noValidate data-testid="coupon-form">
      <TextField label={t('market.code')} maxLength={32} value={code} onChange={(e) => setCode(e.target.value)} />
      <Select label={t('market.kind')} value={kind} onChange={(e) => setKind(e.target.value as DiscountKind)}>
        <option value="PERCENT">{t('market.kinds.PERCENT')}</option>
        <option value="FIXED">{t('market.kinds.FIXED')}</option>
      </Select>
      <TextField label={kind === 'PERCENT' ? t('market.percent') : t('market.amount')} type="number" min={1} inputMode="numeric" value={value} onChange={(e) => setValue(e.target.value)} />
      <TextField label={t('market.minOrder')} optional type="number" min={0} inputMode="numeric" value={minimum} onChange={(e) => setMinimum(e.target.value)} />
      <TextField label={t('market.days')} type="number" min={1} inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value)} />
      <TextField label={t('market.maxUses')} optional type="number" min={1} inputMode="numeric" value={uses} onChange={(e) => setUses(e.target.value)} />
      <Button type="submit" size="sm" loading={busy} disabled={!code.trim() || !value}>{t('market.createCoupon')}</Button>
    </form>
  )
}

function PromotionsTab({ company }: { company?: string }) {
  const { t, i18n } = useTranslation()
  const money = useMoney()
  const { error, fail, clear } = useErrors()
  const [version, setVersion] = useState(0)
  const inventory = useAsyncData((signal) => commerce.listInventory(company, signal), [company])
  const [product, setProduct] = useState('')
  const [percent, setPercent] = useState('10')
  const [days, setDays] = useState('14')
  const bump = () => {
    clear()
    setVersion((v) => v + 1)
  }
  return (
    <>
      <Alert kind="info">{t('market.sellerFunded')}</Alert>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <SectionCard headingLevel={2} title={t('market.coupons')}>
        <CouponForm onCreate={(input) => commerce.createSellerCoupon(input, company).then(bump)} onError={fail} />
        <AsyncPage load={(signal) => commerce.listSellerCoupons(company, signal)} deps={[company, version]}>
          {(page, reload) =>
            page.results.length === 0 ? <p className="text-caption">{t('market.noCoupons')}</p> : (
              <div className="table-scroll">
                <table className="data-table" data-testid="coupon-table">
                  <thead><tr><th scope="col">{t('market.code')}</th><th scope="col">{t('market.discount')}</th><th scope="col" className="num">{t('market.used')}</th><th scope="col">{t('market.validUntil')}</th><th scope="col" /></tr></thead>
                  <tbody>
                    {page.results.map((c) => {
                      const expired = new Date(c.ends_at) < new Date()
                      return (
                        <tr key={c.id}>
                          <td className="ltr"><strong>{c.code}</strong></td>
                          <td>{c.kind === 'PERCENT' ? `${Number(c.value)}%` : money(c.value)}{Number(c.min_subtotal) > 0 ? ` · ${t('market.minOrder')} ${money(c.min_subtotal)}` : ''}</td>
                          <td className="num">{c.redemptions}{c.max_redemptions ? ` / ${c.max_redemptions}` : ''}</td>
                          <td>{new Date(c.ends_at).toLocaleDateString(i18n.language)} {!c.is_active ? <Badge tone="neutral">{t('market.stopped')}</Badge> : expired ? <Badge tone="neutral">{t('market.expired')}</Badge> : <Badge tone="success">{t('market.active')}</Badge>}</td>
                          <td>{c.is_active && !expired ? <ApiActionButton size="sm" variant="ghost" action={() => commerce.stopSellerCoupon(c.id, company)} onSuccess={reload} onError={fail}>{t('market.stop')}</ApiActionButton> : null}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )
          }
        </AsyncPage>
      </SectionCard>
      <SectionCard headingLevel={2} title={t('market.sales')}>
        <form
          className="cluster"
          style={{ alignItems: 'flex-end' }}
          noValidate
          onSubmit={async (event) => {
            event.preventDefault()
            try {
              await commerce.createSale(product, percent, inDays(Number(days) || 14), company)
              bump()
            } catch (e) {
              fail(e)
            }
          }}
        >
          <Select label={t('market.product')} value={product} onChange={(e) => setProduct(e.target.value)}>
            <option value="">{t('market.chooseProduct')}</option>
            {(inventory.data ?? []).filter((p) => p.price).map((p) => (
              <option key={p.id} value={p.id}>{pickScript(p.title, i18n.language)}</option>
            ))}
          </Select>
          <TextField label={t('market.percent')} type="number" min={1} max={90} inputMode="numeric" value={percent} onChange={(e) => setPercent(e.target.value)} />
          <TextField label={t('market.days')} type="number" min={1} inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value)} />
          <Button type="submit" size="sm" disabled={!product || !percent}>{t('market.createSale')}</Button>
        </form>
        <AsyncPage load={(signal) => commerce.listSales(company, signal)} deps={[company, version]}>
          {(page, reload) =>
            page.results.length === 0 ? <p className="text-caption">{t('market.noSales')}</p> : (
              <ul className="stack-sm" style={{ margin: 0, paddingInlineStart: '1.25rem' }}>
                {page.results.map((s) => (
                  <li key={s.id} className="cluster">
                    <span>{pickScript(s.product.title, i18n.language)} — <strong>{Number(s.percent)}%</strong> · {t('market.validUntil')} {new Date(s.ends_at).toLocaleDateString(i18n.language)}</span>
                    {s.is_active && new Date(s.ends_at) > new Date() ? (
                      <ApiActionButton size="sm" variant="ghost" action={() => commerce.stopSale(s.id, company)} onSuccess={reload} onError={fail}>{t('market.stop')}</ApiActionButton>
                    ) : <Badge tone="neutral">{t('market.stopped')}</Badge>}
                  </li>
                ))}
              </ul>
            )
          }
        </AsyncPage>
      </SectionCard>
    </>
  )
}

// ---- finance (merchant statement) -------------------------------------------------------------------
function FinanceTab({ company }: { company?: string }) {
  const { t, i18n } = useTranslation()
  const money = useMoney()
  return (
    <AsyncPage load={(signal) => commerce.getStatement(company, signal)} deps={[company]}>
      {(s) => (
        <>
          <Alert kind="info">{t('market.statementInfo', { rate: Number(s.commission_rate) })}</Alert>
          <div className="grid-auto" data-testid="statement-cards" style={{ display: 'grid', gap: 'var(--space-3)', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))' }}>
            <StatCard label={t('market.grossSales')} value={money(s.gross_sales)} />
            <StatCard label={t('market.sellerDiscounts')} value={money(s.seller_discounts)} />
            <StatCard label={t('market.commissionBase')} value={money(s.merchandise_net)} />
            <StatCard label={t('market.commission', { rate: Number(s.commission_rate) })} value={money(s.commission)} hint={Number(s.refunded_commission) ? t('market.minusRefunded', { amount: money(s.refunded_commission) }) : undefined} />
            <StatCard label={t('market.earnings')} value={money(s.seller_earnings)} />
            <StatCard label={t('market.paidOut')} value={money(s.paid_out)} />
            <StatCard label={t('market.owedNow')} value={money(s.payable)} hint={s.draft_settlement ? t('market.payoutPrepared', { amount: money(s.draft_settlement.amount) }) : undefined} />
            {Number(s.receivable) > 0 ? <StatCard label={t('market.youOwe')} value={money(s.receivable)} hint={t('market.youOweHint')} /> : null}
            <StatCard label={t('market.pending')} value={money(s.pending_seller_payable)} hint={t('market.pendingOrders', { count: s.pending_orders })} />
          </div>
          <SectionCard headingLevel={2} title={t('market.payouts')}>
            {s.settlements.length === 0 ? <p className="text-caption">{t('market.noPayouts')}</p> : (
              <ul className="stack-sm" style={{ margin: 0, paddingInlineStart: '1.25rem' }}>
                {s.settlements.map((b) => (
                  <li key={b.id}>
                    <strong className="ltr">{money(b.amount)}</strong> · <Badge tone={b.status === 'PAID' ? 'success' : b.status === 'DRAFT' ? 'warning' : 'neutral'}>{t(`market.settlementStatus.${b.status}`)}</Badge>{' '}
                    {b.confirmed_at ? new Date(b.confirmed_at).toLocaleDateString(i18n.language) : null} {b.reference_note ? <span className="text-caption ltr">{b.reference_note}</span> : null}
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
          <SectionCard headingLevel={2} title={t('market.ledgerLines')}>
            <div className="table-scroll">
              <table className="data-table" data-testid="statement-entries">
                <thead><tr><th scope="col">{t('market.when')}</th><th scope="col">{t('market.entry')}</th><th scope="col">{t('market.order')}</th><th scope="col" className="num">{t('market.owedMore')}</th><th scope="col" className="num">{t('market.owedLess')}</th></tr></thead>
                <tbody>
                  {s.entries.map((e) => (
                    <tr key={`${e.reference}-${e.account}-${e.debit}-${e.credit}`}>
                      <td>{new Date(e.created_at).toLocaleString(i18n.language)}</td>
                      <td>{t(`market.entryKind.${e.kind}`)}{e.account === 'SELLER_RECEIVABLE' ? <> · <Badge tone="warning">{t('market.receivableLine')}</Badge></> : null}</td>
                      <td className="ltr">{e.order_number || '—'}</td>
                      <td className="num ltr">{Number(e.credit) ? money(e.credit) : ''}</td>
                      <td className="num ltr">{Number(e.debit) ? money(e.debit) : ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </>
      )}
    </AsyncPage>
  )
}
