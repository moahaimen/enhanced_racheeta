import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router'

import { commerce } from '../../api'
import type { InvoiceDocument, InvoiceSummary } from '../../api'
import { AsyncPage, Badge, Button, Container, EmptyState, Icon, PageHeader } from '../../design-system'
import { pickScript } from '../../i18n/localized'
import { useMoney } from '../market/money'
import styles from './documents.module.css'

/** /orders/:orderId/documents — the buyer's invoice, receipt and credit notes for one order. */
export function MyOrderDocumentsPage() {
  const { orderId = '' } = useParams()
  return (
    <DocumentsView
      back="/orders"
      list={(signal) => commerce.listMyInvoices(orderId, signal)}
      get={(id, signal) => commerce.getMyInvoice(orderId, id, signal)}
      deps={[orderId]}
    />
  )
}

/** /merchant/orders/:orderId/documents[?company=] — the same documents, for the seller's team. */
export function SellerOrderDocumentsPage() {
  const { orderId = '' } = useParams()
  const [params] = useSearchParams()
  const company = params.get('company') ?? undefined
  return (
    <DocumentsView
      back={`/merchant/orders${company ? `?company=${encodeURIComponent(company)}` : ''}`}
      list={(signal) => commerce.listSellerInvoices(orderId, company, signal)}
      get={(id, signal) => commerce.getSellerInvoice(orderId, id, company, signal)}
      deps={[orderId, company]}
    />
  )
}

function DocumentsView({
  back,
  list,
  get,
  deps,
}: {
  back: string
  list: (signal: AbortSignal) => Promise<InvoiceSummary[]>
  get: (id: string, signal: AbortSignal) => Promise<InvoiceDocument>
  deps: unknown[]
}) {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<string | null>(null)
  return (
    <Container width="lg">
      <div className="no-print">
        <PageHeader
          eyebrow={
            <Link to={back} className="cluster">
              <Icon name="chevronBack" size={14} flipInRtl /> {t('store.myOrders')}
            </Link>
          }
          title={t('market.documents')}
          description={t('market.documentsIntro')}
        />
      </div>
      <AsyncPage load={list} deps={deps}>
        {(docs) =>
          docs.length === 0 ? (
            <div className="card-block"><EmptyState icon="clipboard" title={t('market.noDocuments')} /></div>
          ) : (
            <>
              <div className="cluster no-print" role="tablist" aria-label={t('market.documents')} data-testid="document-tabs">
                {docs.map((d) => {
                  const active = (selected ?? docs[0]!.id) === d.id
                  return (
                    <Button key={d.id} role="tab" aria-selected={active} size="sm" variant={active ? 'primary' : 'secondary'} onClick={() => setSelected(d.id)}>
                      {t(`market.documentKind.${d.kind}`)} <span className="ltr">{d.number}</span>
                    </Button>
                  )
                })}
              </div>
              <AsyncPage load={(signal) => get(selected ?? docs[0]!.id, signal)} deps={[selected ?? docs[0]!.id]}>
                {(doc) => <PrintableDocument doc={doc} />}
              </AsyncPage>
            </>
          )
        }
      </AsyncPage>
    </Container>
  )
}

/** A printable buyer document, rendered only from the frozen server snapshot. */
export function PrintableDocument({ doc }: { doc: InvoiceDocument }) {
  const { t, i18n } = useTranslation()
  const money = useMoney()
  const s = doc.snapshot
  const lang = i18n.language
  const showTax = s.tax.mode === 'EXCLUSIVE' && Number(s.totals.tax) > 0
  return (
    <article className={styles.sheet} data-testid="printable-document" aria-label={t(`market.documentKind.${doc.kind}`)}>
      <header className={styles.head}>
        <div>
          <p className={styles.brand}>Racheeta · رشيتة</p>
          <h1 className={styles.title}>{t(`market.documentKind.${doc.kind}`)}</h1>
          <p className="ltr">{doc.number}</p>
        </div>
        <div className={styles.meta}>
          <p>{t('market.issuedAt')}: <time dateTime={s.issued_at}>{new Date(s.issued_at).toLocaleString(lang)}</time></p>
          <p>{t('market.orderNo')}: <span className="ltr">{s.order.number}</span></p>
          {s.order.paid_at ? <p>{t('market.paidAt')}: {new Date(s.order.paid_at).toLocaleString(lang)}</p> : null}
          <p>{t(`store.paymentMethods.${s.order.payment_method}`)}{s.order.payment_reference ? ` · ${s.order.payment_reference}` : ''}</p>
        </div>
      </header>
      <div className={styles.parties}>
        <section>
          <h2>{t('market.seller')}</h2>
          <p><strong>{pickScript(s.seller.name, lang)}</strong></p>
          <p>{t(`accountTypes.${s.seller.business_type}`, { defaultValue: s.seller.business_type })}</p>
          <p>{[s.seller.address, s.seller.governorate].filter(Boolean).join(' · ')}</p>
          {s.seller.phone ? <p className="ltr">{s.seller.phone}</p> : null}
          {s.seller.tax_registration_number ? <p>{t('market.taxNumber')}: <span className="ltr">{s.seller.tax_registration_number}</span></p> : null}
        </section>
        <section>
          <h2>{t('market.buyer')}</h2>
          <p><strong>{s.buyer.name}</strong></p>
          <p>{[s.buyer.address, s.buyer.city, s.buyer.governorate].filter(Boolean).join(' · ')}</p>
          <p className="ltr">{s.buyer.phone}</p>
        </section>
      </div>
      <div className="table-scroll">
        <table className={`data-table ${styles.lines}`}>
          <thead>
            <tr>
              <th scope="col">{t('market.item')}</th>
              <th scope="col">{t('market.qty')}</th>
              <th scope="col">{t('market.unitPrice')}</th>
              <th scope="col">{t('market.discount')}</th>
              {showTax ? <th scope="col">{s.tax.label || t('market.tax')}</th> : null}
              <th scope="col">{t('market.lineTotal')}</th>
            </tr>
          </thead>
          <tbody>
            {s.lines.map((line, i) => (
              <tr key={i}>
                <td>
                  {pickScript(line.title, lang)}
                  {line.variant ? <span className="text-caption"> · {line.variant}</span> : null}
                  {line.sku ? <div className="text-caption ltr">{line.sku}</div> : null}
                  {line.refunded_quantity ? <Badge tone="neutral">{t('market.refundedUnits', { count: line.refunded_quantity })}</Badge> : null}
                </td>
                <td className="ltr">{line.quantity}</td>
                <td className="ltr">{money(line.unit_price, s.currency)}</td>
                <td className="ltr">{money(Number(line.seller_discount) + Number(line.platform_discount), s.currency)}</td>
                {showTax ? <td className="ltr">{money(line.tax, s.currency)}</td> : null}
                <td className="ltr">{money(line.total, s.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <table className={`money-table ${styles.totals}`}>
        <tbody>
          <tr><th scope="row">{t('market.listTotal')}</th><td className="ltr">{money(s.totals.list, s.currency)}</td></tr>
          {Number(s.totals.seller_discount) ? <tr><th scope="row">{t('market.sellerDiscount')}</th><td className="ltr">− {money(s.totals.seller_discount, s.currency)}</td></tr> : null}
          {Number(s.totals.platform_discount) ? <tr><th scope="row">{t('market.racheetaDiscount')}</th><td className="ltr">− {money(s.totals.platform_discount, s.currency)}</td></tr> : null}
          {Number(s.totals.shipping) ? <tr><th scope="row">{t('market.deliveryFee')}</th><td className="ltr">{money(s.totals.shipping, s.currency)}</td></tr> : null}
          {showTax ? <tr><th scope="row">{s.tax.label || t('market.tax')} ({Number(s.tax.rate)}%)</th><td className="ltr">{money(s.totals.tax, s.currency)}</td></tr> : null}
          <tr className="money-strong"><th scope="row">{t('market.total')}</th><td className="ltr">{money(s.totals.total, s.currency)}</td></tr>
          {s.refund ? <tr className="money-strong"><th scope="row">{t('market.refundAmount')}</th><td className="ltr">{money(s.refund.amount, s.currency)}</td></tr> : null}
        </tbody>
      </table>
      {s.tax.mode === 'INCLUSIVE' && Number(s.tax.included) > 0 ? (
        <p className="text-caption">{t('market.taxIncluded', { amount: money(s.tax.included, s.currency), label: s.tax.label || t('market.tax') })}</p>
      ) : null}
      {s.refund ? <p className="text-caption">{t('market.reason')}: {s.refund.reason}</p> : null}
      <footer className={styles.foot}>
        <p>{t('market.sellerOfRecord')}</p>
        <p className={styles.notice}>{t('market.documentNotice')}</p>
      </footer>
      <div className="no-print">
        <Button leading={<Icon name="clipboard" size={16} />} onClick={() => window.print()} data-testid="print-document">
          {t('market.print')}
        </Button>
      </div>
    </article>
  )
}
