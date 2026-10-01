import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { PAYMENT_METHODS, advertising as advertisingApi, CAMPAIGN_STATUSES } from '../../api'
import type { AdminCampaign, CampaignPaymentMethod, CampaignStatus } from '../../api'
import type { BadgeTone } from '../../design-system'
import { Alert, ApiActionButton, AsyncPage, Badge, EmptyState, Icon, Pagination, SectionCard, Select, TextField } from '../../design-system'
import { useLocalizedName } from '../../i18n/localized'
import { formatMoney, refusalMessage } from '../advertising/advertisingFormat'
import { TargetingSummary } from '../advertising/TargetingSummary'
import styles from './AdminConsolePage.module.css'

const ALL = 'ALL'

/** Advertising / campaign payments: administrators confirm or reject the off-platform payment. The amount is the campaign's own quote. */
export function AdminAdvertisingTab() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const filter = params.get('filter') ?? 'PENDING_PAYMENT'
  const set = (patch: { page?: number; filter?: string }) => {
    const next = new URLSearchParams(params)
    if (patch.filter !== undefined) {
      next.set('filter', patch.filter)
      next.delete('page')
    }
    if (patch.page !== undefined) {
      if (patch.page > 1) next.set('page', String(patch.page))
      else next.delete('page')
    }
    setParams(next)
  }
  return (
    <SectionCard title={t('admin.tabs.advertising')} description={t('admin.advertising.intro')} headingLevel={2}>
      <div className={styles.filters}>
        <Select label={t('admin.advertising.statusFilter')} value={filter} onChange={(e) => set({ filter: e.target.value })}>
          <option value={ALL}>{t('common.all')}</option>
          {CAMPAIGN_STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`campaignStatus.${s}`)}
            </option>
          ))}
        </Select>
      </div>
      <AsyncPage load={(signal) => advertisingApi.listAdminCampaigns({ status: filter === ALL ? '' : (filter as CampaignStatus), page }, signal)} deps={[filter, page]}>
        {(res, reload) => (
          <>
            {res.results.length === 0 ? <EmptyState icon="tag" title={t('admin.advertising.empty')} testId="admin-empty-campaigns" /> : null}
            <ul className={styles.list}>
              {res.results.map((c) => (
                <CampaignRow key={c.id} campaign={c} reload={reload} />
              ))}
            </ul>
            <Pagination page={page} total={Math.max(1, Math.ceil(res.count / 20))} hasNext={res.next !== null} hasPrevious={res.previous !== null} onChange={(p) => set({ page: p })} />
          </>
        )}
      </AsyncPage>
    </SectionCard>
  )
}

const TONE: Record<CampaignStatus, BadgeTone> = { DRAFT: 'neutral', PENDING_PAYMENT: 'warning', ACTIVE: 'success', REJECTED: 'error', CANCELLED: 'neutral' }

function CampaignRow({ campaign: c, reload }: { campaign: AdminCampaign; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const [method, setMethod] = useState<CampaignPaymentMethod | ''>('')
  const [reference, setReference] = useState('')
  const [note, setNote] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const fail = (e: unknown) => setError(refusalMessage(e, t))
  return (
    <li className={styles.row} data-testid="admin-campaign">
      <div className={styles.rowHead}>
        <span className={styles.rowTitle}>
          {c.name} · {c.product.title}
        </span>
        <Badge tone={TONE[c.status]}>{t(`campaignStatus.${c.status}`)}</Badge>
      </div>
      <dl className={styles.meta}>
        <div>
          <dt>{t('admin.advertising.company')}</dt>
          <dd>{c.company.name}</dd>
        </div>
        <div>
          <dt>{t('admin.advertising.account')}</dt>
          <dd dir="ltr">{c.company.account_email}</dd>
        </div>
        <div>
          <dt>{t('admin.advertising.category')}</dt>
          <dd>{name(c.product.category)}</dd>
        </div>
        <div>
          <dt>{t('admin.advertising.dates')}</dt>
          <dd dir="ltr">{c.starts_on && c.ends_on ? `${c.starts_on} → ${c.ends_on}` : '—'}</dd>
        </div>
        {c.quote ? (
          <>
            <div>
              <dt>{t('admin.advertising.dailyRate')}</dt>
              <dd dir="auto" data-testid="admin-quote-rate">{formatMoney(c.quote.daily_rate, c.quote.currency, i18n.language)}</dd>
            </div>
            <div>
              <dt>{t('admin.advertising.days')}</dt>
              <dd data-testid="admin-quote-days">{c.quote.days}</dd>
            </div>
            <div>
              <dt>{t('admin.advertising.amount')}</dt>
              <dd dir="auto" data-testid="admin-quote-amount">{formatMoney(c.quote.amount, c.quote.currency, i18n.language)}</dd>
            </div>
          </>
        ) : null}
        <div>
          <dt>{t('admin.advertising.payment')}</dt>
          <dd data-testid="admin-payment-status">{c.payment ? t(`paymentStatus.${c.payment.status}`) : '—'}</dd>
        </div>
      </dl>
      <TargetingSummary campaign={c} />
      {c.payment && c.payment.status !== 'PENDING' ? (
        <p className="text-caption">
          {c.payment.method ? t(`paymentMethods.${c.payment.method}`) : ''} {c.payment.reference ? `· ${c.payment.reference}` : ''}
          {c.payment.verified_by_email ? ` · ${c.payment.verified_by_email}` : ''}
          {c.payment.admin_note ? ` · ${c.payment.admin_note}` : ''}
        </p>
      ) : null}
      {error ? <Alert kind="error">{error}</Alert> : null}
      {c.status === 'PENDING_PAYMENT' ? (
        <>
          <p className="text-caption">{t('admin.advertising.amountNote')}</p>
          <div className={styles.actions}>
            <Select label={t('admin.advertising.method')} value={method} onChange={(e) => setMethod(e.target.value as CampaignPaymentMethod | '')}>
              <option value="">{t('admin.advertising.chooseMethod')}</option>
              {PAYMENT_METHODS.map((m) => (
                <option key={m} value={m}>
                  {t(`paymentMethods.${m}`)}
                </option>
              ))}
            </Select>
            <TextField label={t('admin.advertising.reference')} dir="ltr" value={reference} onChange={(e) => setReference(e.target.value)} />
            <TextField label={t('admin.note')} value={note} onChange={(e) => setNote(e.target.value)} />
            <ApiActionButton
              size="sm"
              action={async () => {
                if (!method) throw new Error(t('admin.advertising.chooseMethod'))
                return advertisingApi.verifyCampaignPayment(c.id, { method, reference: reference.trim(), note: note.trim() })
              }}
              onSuccess={() => {
                setError(null)
                reload()
              }}
              onError={fail}
              leading={<Icon name="check" size={16} />}
              pendingLabel={t('admin.advertising.verifying')}
            >
              {t('admin.advertising.verify')}
            </ApiActionButton>
          </div>
          <div className={styles.actions}>
            <TextField label={t('admin.advertising.reason')} value={reason} onChange={(e) => setReason(e.target.value)} />
            <ApiActionButton
              size="sm"
              variant="danger"
              action={() => advertisingApi.rejectCampaignPayment(c.id, reason.trim())}
              onSuccess={() => {
                setError(null)
                reload()
              }}
              onError={fail}
              pendingLabel={t('admin.advertising.rejecting')}
            >
              {t('admin.advertising.reject')}
            </ApiActionButton>
          </div>
        </>
      ) : null}
    </li>
  )
}
