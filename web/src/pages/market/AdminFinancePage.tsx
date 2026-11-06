import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { ApiError, commerce } from '../../api'
import type { Order } from '../../api'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Badge,
  Container,
  EmptyState,
  Icon,
  PageHeader,
  PageStack,
  SectionCard,
  Select,
  StatCard,
  Tabs,
  TextField,
  tabPanelProps,
} from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import { pickScript } from '../../i18n/localized'
import { OrderCard } from '../store/OrdersPages'
import { RETURN_TONE } from './tones'
import { CouponForm } from './SellerCenterPage'
import { useMoney } from './money'

const TABS = ['orders', 'returns', 'disputes', 'settlements', 'reconciliation', 'coupons', 'ledger', 'policy'] as const
type Tab = (typeof TABS)[number]

/**
 * /admin-finance — Racheeta's central control of marketplace money (SIMULATED: no real payments).
 * Only staff WITH the finance permission get data; other staff see the server's refusal.
 */
export function AdminFinancePage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const raw = params.get('tab')
  const tab: Tab = TABS.includes(raw as Tab) ? (raw as Tab) : 'orders'
  return (
    <Container width="xl">
      <PageHeader eyebrow={<><Icon name="shieldCheck" size={16} />{t('admin.eyebrow')}</>} title={t('market.finance.title')} description={t('market.finance.intro')} />
      <Alert kind="warning">{t('market.finance.simulated')}</Alert>
      <Tabs id="finance" aria-label={t('market.finance.title')} value={tab} onChange={(next) => setParams({ tab: next })} tabs={TABS.map((id) => ({ id, label: t(`market.finance.tabs.${id}`) }))} />
      <div {...tabPanelProps('finance', tab)}>
        <PageStack>
          {tab === 'orders' ? <OrdersTab /> : tab === 'returns' ? <ReturnsTab /> : tab === 'disputes' ? <DisputesTab /> : tab === 'settlements' ? <SettlementsTab /> : tab === 'reconciliation' ? <ReconciliationTab /> : tab === 'coupons' ? <CouponsTab /> : tab === 'ledger' ? <LedgerTab /> : <PolicyTab />}
        </PageStack>
      </div>
    </Container>
  )
}

function useErrors() {
  const { t } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  return {
    error,
    fail: (e: unknown) => setError(e instanceof ApiError && e.status === 403 ? t('market.finance.forbidden') : toErrorMessage(e)),
    clear: () => setError(null),
  }
}

const QUEUES: Record<string, Record<string, string>> = {
  awaitingPayment: { payment_status: 'UNPAID' },
  awaitingCompletion: { status: 'DELIVERED' },
  shipped: { status: 'SHIPPED' },
  refundPending: { payment_status: 'REFUND_PENDING' },
  completed: { status: 'COMPLETED' },
  all: {},
}

function OrdersTab() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const queue = params.get('queue') && QUEUES[params.get('queue')!] ? params.get('queue')! : 'awaitingPayment'
  const { error, fail, clear } = useErrors()
  return (
    <>
      <Select label={t('market.finance.queue')} value={queue} onChange={(e) => setParams({ tab: 'orders', queue: e.target.value })}>
        {Object.keys(QUEUES).map((key) => (
          <option key={key} value={key}>{t(`market.finance.queues.${key}`)}</option>
        ))}
      </Select>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <AsyncPage load={(signal) => commerce.listAdminOrders(QUEUES[queue]!, 1, signal)} deps={[queue]}>
        {(page, reload) =>
          page.results.length === 0 ? (
            <div className="card-block"><EmptyState icon="checkCircle" title={t('market.finance.empty')} /></div>
          ) : (
            page.results.map((order) => (
              <OrderCard key={order.id} order={order} seller>
                <p className="text-caption">{t('store.buyer')}: {order.buyer_name}{order.payment_reference ? <> · {t('market.finance.reference')}: <span className="ltr">{order.payment_reference}</span></> : null}</p>
                <FinanceActions order={order} onDone={() => { clear(); reload() }} onError={fail} />
              </OrderCard>
            ))
          )
        }
      </AsyncPage>
    </>
  )
}

function FinanceActions({ order, onDone, onError }: { order: Order; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const [reference, setReference] = useState('')
  const paid = ['PAID', 'PARTIALLY_REFUNDED'].includes(order.payment_status)
  return (
    <div className="cluster" style={{ alignItems: 'flex-end' }}>
      {order.payment_status === 'UNPAID' && order.status !== 'CANCELLED' ? (
        <>
          <TextField label={t('market.finance.paymentReference')} maxLength={120} value={reference} onChange={(e) => setReference(e.target.value)} hint={t('market.finance.referenceHint')} />
          <ApiActionButton size="sm" disabled={!reference.trim()} action={() => commerce.verifyPayment(order.id, reference.trim())} onSuccess={onDone} onError={onError} leading={<Icon name="checkCircle" size={14} />}>
            {t('market.finance.verifyPayment')}
          </ApiActionButton>
        </>
      ) : null}
      {order.status === 'SHIPPED' ? (
        <ApiActionButton size="sm" variant="secondary" action={() => commerce.financeConfirmDelivery(order.id)} onSuccess={onDone} onError={onError}>
          {t('market.finance.confirmDelivery')}
        </ApiActionButton>
      ) : null}
      {order.status === 'DELIVERED' && paid ? (
        <ApiActionButton size="sm" action={() => commerce.completeOrder(order.id)} onSuccess={onDone} onError={onError} leading={<Icon name="calculator" size={14} />}>
          {t('market.finance.complete')}
        </ApiActionButton>
      ) : null}
      {order.status === 'CANCELLED' && order.payment_status === 'REFUND_PENDING' ? (
        <ApiActionButton size="sm" action={() => commerce.refundCancelled(order.id)} onSuccess={onDone} onError={onError}>
          {t('market.finance.refundCancelled')}
        </ApiActionButton>
      ) : null}
    </div>
  )
}

function ReturnsTab() {
  const { t, i18n } = useTranslation()
  const [status, setStatus] = useState('RECEIVED')
  const { error, fail, clear } = useErrors()
  return (
    <>
      <Select label={t('market.finance.status')} value={status} onChange={(e) => setStatus(e.target.value)}>
        {['RECEIVED', 'REQUESTED', 'APPROVED', 'REFUNDED', 'REJECTED', ''].map((s) => (
          <option key={s} value={s}>{s ? t(`market.returnStatus.${s}`) : t('market.finance.queues.all')}</option>
        ))}
      </Select>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <AsyncPage load={(signal) => commerce.listAdminReturns(status || undefined, signal)} deps={[status]}>
        {(page, reload) =>
          page.results.length === 0 ? <div className="card-block"><EmptyState icon="refresh" title={t('market.noReturns')} /></div> : (
            page.results.map((r) => (
              <SectionCard key={r.id} headingLevel={2} title={<span className="ltr">{r.order.number}</span>} actions={<Badge tone={RETURN_TONE[r.status]}>{t(`market.returnStatus.${r.status}`)}</Badge>}>
                <p>{r.lines.map((l) => `${pickScript(l.title, i18n.language)} × ${l.quantity}`).join(', ')} — {r.reason}</p>
                {r.status === 'RECEIVED' ? (
                  <ApiActionButton size="sm" action={() => commerce.refundReturn(r.id)} onSuccess={() => { clear(); reload() }} onError={fail}>
                    {t('market.finance.refundReturn')}
                  </ApiActionButton>
                ) : null}
              </SectionCard>
            ))
          )
        }
      </AsyncPage>
    </>
  )
}

function DisputesTab() {
  const { t } = useTranslation()
  const { error, fail, clear } = useErrors()
  const [notes, setNotes] = useState<Record<string, string>>({})
  return (
    <>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <AsyncPage load={(signal) => commerce.listDisputes(undefined, signal)}>
        {(page, reload) =>
          page.results.length === 0 ? <div className="card-block"><EmptyState icon="checkCircle" title={t('market.finance.noDisputes')} /></div> : (
            page.results.map((d) => (
              <SectionCard key={d.id} headingLevel={2} title={<span className="ltr">{d.order.number}</span>} actions={<Badge tone={d.status === 'OPEN' ? 'warning' : 'neutral'}>{t(`market.disputeStatus.${d.status}`)}</Badge>}>
                <p>{d.reason}</p>
                {d.resolution_note ? <p className="text-caption">{d.resolution_note}</p> : null}
                {d.status === 'OPEN' ? (
                  <div className="cluster" style={{ alignItems: 'flex-end' }}>
                    <TextField label={t('market.finance.resolution')} maxLength={500} value={notes[d.id] ?? ''} onChange={(e) => setNotes({ ...notes, [d.id]: e.target.value })} />
                    <ApiActionButton size="sm" disabled={!notes[d.id]?.trim()} action={() => commerce.resolveDispute(d.id, true, notes[d.id]!.trim())} onSuccess={() => { clear(); reload() }} onError={fail}>
                      {t('market.finance.resolveRefund')}
                    </ApiActionButton>
                    <ApiActionButton size="sm" variant="ghost" disabled={!notes[d.id]?.trim()} action={() => commerce.resolveDispute(d.id, false, notes[d.id]!.trim())} onSuccess={() => { clear(); reload() }} onError={fail}>
                      {t('market.finance.resolveReject')}
                    </ApiActionButton>
                  </div>
                ) : null}
              </SectionCard>
            ))
          )
        }
      </AsyncPage>
    </>
  )
}

function SettlementsTab() {
  const { t, i18n } = useTranslation()
  const money = useMoney()
  const { error, fail, clear } = useErrors()
  const [version, setVersion] = useState(0)
  const [notes, setNotes] = useState<Record<string, string>>({})
  const done = () => {
    clear()
    setVersion((v) => v + 1)
  }
  return (
    <>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <SectionCard headingLevel={2} title={t('market.finance.owedToSellers')}>
        <AsyncPage load={(signal) => commerce.listPayables(signal)} deps={[version]}>
          {(rows) =>
            rows.length === 0 ? <p className="text-caption">{t('market.finance.nothingOwed')}</p> : (
              <div className="table-scroll">
                <table className="data-table" data-testid="payables-table">
                  <thead><tr><th scope="col">{t('market.finance.seller')}</th><th scope="col" className="num">{t('market.finance.owed')}</th><th scope="col" className="num">{t('market.finance.sellerOwes')}</th><th scope="col" /></tr></thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.company.id}>
                        <td>{pickScript(row.company.name, i18n.language)}</td>
                        <td className="num ltr"><strong>{money(row.payable)}</strong></td>
                        <td className="num ltr">{Number(row.receivable) > 0 ? <Badge tone="warning">{money(row.receivable)}</Badge> : '—'}</td>
                        <td>
                          {Number(row.payable) > 0 ? (
                            <ApiActionButton size="sm" variant="secondary" action={() => commerce.prepareSettlement(row.company.id)} onSuccess={done} onError={fail}>
                              {row.draft_settlement ? t('market.finance.refreshPayout') : t('market.finance.preparePayout')}
                            </ApiActionButton>
                          ) : null}
                          {Number(row.receivable) > 0 ? <RecoveryForm companyId={row.company.id} owed={row.receivable} onDone={done} onError={fail} /> : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        </AsyncPage>
      </SectionCard>
      <SectionCard headingLevel={2} title={t('market.payouts')}>
        <AsyncPage load={(signal) => commerce.listSettlements(signal)} deps={[version]}>
          {(page) =>
            page.results.length === 0 ? <p className="text-caption">{t('market.noPayouts')}</p> : (
              <div className="stack-sm">
                {page.results.map((b) => (
                  <div key={b.id} className="cluster card-block" style={{ alignItems: 'flex-end' }} data-testid="settlement-row">
                    <span>
                      <strong>{pickScript(b.company.name, i18n.language)}</strong> · <span className="ltr">{money(b.amount)}</span>{' '}
                      <Badge tone={b.status === 'PAID' ? 'success' : b.status === 'DRAFT' ? 'warning' : 'neutral'}>{t(`market.settlementStatus.${b.status}`)}</Badge>{' '}
                      {b.confirmed_by ? <span className="text-caption">{b.confirmed_by} · {b.reference_note}</span> : null}
                    </span>
                    {b.status === 'DRAFT' ? (
                      <>
                        <TextField label={t('market.finance.transferReference')} maxLength={200} value={notes[b.id] ?? ''} onChange={(e) => setNotes({ ...notes, [b.id]: e.target.value })} hint={t('market.finance.referenceHint')} />
                        <ApiActionButton size="sm" disabled={!notes[b.id]?.trim()} action={() => commerce.confirmSettlement(b.id, notes[b.id]!.trim())} onSuccess={done} onError={fail}>
                          {t('market.finance.markPaid')}
                        </ApiActionButton>
                        <ApiActionButton size="sm" variant="ghost" action={() => commerce.cancelSettlement(b.id)} onSuccess={done} onError={fail}>
                          {t('market.finance.cancelPayout')}
                        </ApiActionButton>
                      </>
                    ) : null}
                  </div>
                ))}
              </div>
            )
          }
        </AsyncPage>
      </SectionCard>
    </>
  )
}

function ReconciliationTab() {
  const { t } = useTranslation()
  const money = useMoney()
  return (
    <AsyncPage load={(signal) => commerce.getReconciliation(signal)}>
      {(r) => (
        <>
          <Alert kind={r.ok ? 'success' : 'error'}>{r.ok ? t('market.finance.reconciled') : t('market.finance.notReconciled')}</Alert>
          <div style={{ display: 'grid', gap: 'var(--space-3)', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))' }} data-testid="balances">
            {Object.entries(r.balances).map(([account, value]) => (
              <StatCard key={account} label={t(`market.accounts.${account}`)} value={money(value)} />
            ))}
          </div>
          <div className="card-block table-scroll">
            <table className="data-table" data-testid="reconciliation-checks">
              <thead><tr><th scope="col">{t('market.finance.check')}</th><th scope="col" className="num">{t('market.finance.expected')}</th><th scope="col" className="num">{t('market.finance.actual')}</th><th scope="col">{t('market.finance.result')}</th></tr></thead>
              <tbody>
                {r.checks.map((c) => (
                  <tr key={c.name}>
                    <td>{t(`market.checks.${c.name.split(':')[0]}`, { account: c.name.includes(':') ? t(`market.accounts.${c.name.split(':')[1]}`) : '' })}</td>
                    <td className="num ltr">{c.name.startsWith('balance') ? money(c.expected) : Number(c.expected)}</td>
                    <td className="num ltr">{c.name.startsWith('balance') ? money(c.actual) : Number(c.actual)}</td>
                    <td><Badge tone={c.ok ? 'success' : 'error'}>{c.ok ? t('market.finance.pass') : t('market.finance.fail')}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-caption">{Object.entries(r.totals).map(([k, v]) => `${t(`market.totals.${k}`)}: ${v}`).join(' · ')}</p>
        </>
      )}
    </AsyncPage>
  )
}

function CouponsTab() {
  const { t, i18n } = useTranslation()
  const money = useMoney()
  const { error, fail, clear } = useErrors()
  const [version, setVersion] = useState(0)
  return (
    <>
      <Alert kind="info">{t('market.finance.platformFunded')}</Alert>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <SectionCard headingLevel={2} title={t('market.finance.newPlatformCoupon')}>
        <CouponForm onCreate={(input) => commerce.createPlatformCoupon(input).then(() => { clear(); setVersion((v) => v + 1) })} onError={fail} />
      </SectionCard>
      <AsyncPage load={(signal) => commerce.listAllCoupons(signal)} deps={[version]}>
        {(page, reload) => (
          <div className="card-block table-scroll">
            <table className="data-table" data-testid="all-coupons">
              <thead><tr><th scope="col">{t('market.code')}</th><th scope="col">{t('market.finance.fundedBy')}</th><th scope="col">{t('market.discount')}</th><th scope="col" className="num">{t('market.used')}</th><th scope="col">{t('market.validUntil')}</th><th scope="col" /></tr></thead>
              <tbody>
                {page.results.map((c) => {
                  const expired = new Date(c.ends_at) < new Date()
                  return (
                    <tr key={c.id}>
                      <td className="ltr"><strong>{c.code}</strong></td>
                      <td>{c.funded_by === 'PLATFORM' ? t('market.finance.racheeta') : pickScript(c.company?.name ?? '', i18n.language)}</td>
                      <td>{c.kind === 'PERCENT' ? `${Number(c.value)}%` : money(c.value)}</td>
                      <td className="num">{c.redemptions}{c.max_redemptions ? ` / ${c.max_redemptions}` : ''}</td>
                      <td>{new Date(c.ends_at).toLocaleDateString(i18n.language)} {!c.is_active ? <Badge tone="neutral">{t('market.stopped')}</Badge> : expired ? <Badge tone="neutral">{t('market.expired')}</Badge> : <Badge tone="success">{t('market.active')}</Badge>}</td>
                      <td>{c.funded_by === 'PLATFORM' && c.is_active && !expired ? <ApiActionButton size="sm" variant="ghost" action={() => commerce.stopPlatformCoupon(c.id)} onSuccess={reload} onError={fail}>{t('market.stop')}</ApiActionButton> : null}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </AsyncPage>
    </>
  )
}

function LedgerTab() {
  const { t, i18n } = useTranslation()
  const money = useMoney()
  return (
    <>
      <Alert kind="info">{t('market.finance.immutable')}</Alert>
      <AsyncPage load={(signal) => commerce.listLedgerEntries(1, undefined, signal)}>
        {(page) => (
          <div className="card-block table-scroll">
            <table className="data-table" data-testid="ledger-table">
              <thead><tr><th scope="col">{t('market.when')}</th><th scope="col">{t('market.entry')}</th><th scope="col">{t('market.finance.account')}</th><th scope="col" className="num">{t('market.finance.debit')}</th><th scope="col" className="num">{t('market.finance.credit')}</th></tr></thead>
              <tbody>
                {page.results.flatMap((e) =>
                  e.lines.map((line, i) => (
                    <tr key={`${e.id}-${i}`}>
                      <td>{i === 0 ? new Date(e.created_at).toLocaleString(i18n.language) : ''}</td>
                      <td>{i === 0 ? <>{t(`market.entryKind.${e.kind}`)} <span className="ltr text-caption">{e.order_number}</span></> : ''}</td>
                      <td>{t(`market.accounts.${line.account}`)}{line.company ? ` — ${pickScript(line.company.name, i18n.language)}` : ''}</td>
                      <td className="num ltr">{Number(line.debit) ? money(line.debit) : ''}</td>
                      <td className="num ltr">{Number(line.credit) ? money(line.credit) : ''}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
        )}
      </AsyncPage>
    </>
  )
}

function PolicyTab() {
  const { t, i18n } = useTranslation()
  return (
    <AsyncPage load={(signal) => commerce.listPolicies(signal)}>
      {(rows) => (
        <SectionCard headingLevel={2} title={t('market.finance.policy')}>
          <p className="text-caption">{t('market.finance.policyHint')}</p>
          <ul className="stack-sm" style={{ margin: 0, paddingInlineStart: '1.25rem' }} data-testid="policies">
            {rows.map((p, i) => (
              <li key={p.version}>
                <strong>v{p.version}: {Number(p.rate_percent)}%</strong> — {t('market.finance.since')} {new Date(p.effective_from).toLocaleDateString(i18n.language)}{' '}
                {i === 0 ? <Badge tone="success">{t('market.finance.current')}</Badge> : null} <span className="text-caption">{p.note}</span>
              </li>
            ))}
          </ul>
        </SectionCard>
      )}
    </AsyncPage>
  )
}

/** Finance records that a seller paid back (simulated) what it owes after a refund. */
function RecoveryForm({ companyId, owed, onDone, onError }: { companyId: string; owed: string; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const [amount, setAmount] = useState(String(Math.round(Number(owed))))
  const [note, setNote] = useState('')
  return (
    <div className="cluster" style={{ alignItems: 'flex-end' }} data-testid="recovery-form">
      <TextField label={t('market.finance.recoverAmount')} type="number" min={1} inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} />
      <TextField label={t('market.finance.transferReference')} maxLength={200} value={note} onChange={(e) => setNote(e.target.value)} />
      <ApiActionButton size="sm" variant="secondary" disabled={!note.trim() || !(Number(amount) > 0)} action={() => commerce.recordRecovery(companyId, amount, note.trim())} onSuccess={onDone} onError={onError}>
        {t('market.finance.recordRecovery')}
      </ApiActionButton>
    </div>
  )
}
