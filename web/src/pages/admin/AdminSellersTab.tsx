import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { marketplace as mp } from '../../api'
import type { SellerDocument } from '../../api'
import type { AdminCompany } from '../../api/endpoints/marketplace'
import { Alert, ApiActionButton, AsyncPage, Badge, Button, EmptyState, Icon, SectionCard, Select, TextField } from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import { pickScript } from '../../i18n/localized'

const FILTERS = ['PENDING', 'VERIFIED', 'UNVERIFIED', 'REJECTED', 'SUSPENDED', ''] as const
const DOC_TONE = { PENDING: 'warning', APPROVED: 'success', REJECTED: 'error' } as const

async function openPrivate(url: string) {
  const blob = await mp.fetchPrivateFile(url)
  const href = URL.createObjectURL(blob)
  window.open(href, '_blank', 'noopener,noreferrer')
  window.setTimeout(() => URL.revokeObjectURL(href), 60_000)
}

/** Sellers: Racheeta administrators review licences and decide verification (server-enforced). */
export function AdminSellersTab() {
  const { t } = useTranslation()
  const [filter, setFilter] = useState<string>('PENDING')
  const [error, setError] = useState<string | null>(null)
  return (
    <SectionCard title={t('admin.tabs.sellers')} description={t('sellerSetup.adminIntro')} headingLevel={2}>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <Select label={t('sellerSetup.statusFilter')} value={filter} onChange={(e) => setFilter(e.target.value)}>
        {FILTERS.map((f) => (
          <option key={f || 'all'} value={f}>{f ? t(`verification.${f}`) : t('common.all')}</option>
        ))}
      </Select>
      <AsyncPage load={(signal) => mp.listAdminCompanies(filter, signal)} deps={[filter]}>
        {(page, reload) =>
          page.results.length === 0 ? (
            <EmptyState icon="building" title={t('sellerSetup.noSellers')} />
          ) : (
            <ul className="stack" style={{ listStyle: 'none', padding: 0, margin: 0 }} data-testid="admin-sellers">
              {page.results.map((c) => (
                <SellerRow key={c.id} company={c} onDone={() => { setError(null); reload() }} onError={(e) => setError(toErrorMessage(e))} />
              ))}
            </ul>
          )
        }
      </AsyncPage>
    </SectionCard>
  )
}

function SellerRow({ company, onDone, onError }: { company: AdminCompany; onDone: () => void; onError: (e: unknown) => void }) {
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(company.verification_status === 'PENDING')
  const [note, setNote] = useState('')
  return (
    <li className="card-block stack-sm" data-testid="admin-seller">
      <div className="cluster" style={{ justifyContent: 'space-between' }}>
        <span>
          <strong>{pickScript(company.name, i18n.language)}</strong>{' '}
          <span className="text-caption">{t(`accountTypes.${company.business_type}`, { defaultValue: company.business_type })} · <span className="ltr">{company.account_email}</span></span>
        </span>
        <span className="cluster">
          <Badge tone={company.verification_status === 'VERIFIED' ? 'success' : company.verification_status === 'PENDING' ? 'warning' : 'neutral'}>{t(`verification.${company.verification_status}`)}</Badge>
          <Badge tone={company.store_status === 'ACTIVE' ? 'success' : 'neutral'}>{t(`sellerSetup.storeStatus.${company.store_status ?? 'ACTIVE'}`)}</Badge>
          <Button size="sm" variant="secondary" onClick={() => setOpen(!open)} aria-expanded={open}>{t('sellerSetup.review')}</Button>
        </span>
      </div>
      {open ? (
        <>
          <AsyncPage load={(signal) => mp.listCompanyDocumentsAdmin(company.id, signal)} deps={[company.id]}>
            {(docs, reload) => <DocumentList docs={docs.results} onDone={() => { reload(); onDone() }} onError={onError} />}
          </AsyncPage>
          {(company.missing_documents ?? []).length ? (
            <Alert kind="warning">{t('sellerSetup.missingList', { list: (company.missing_documents ?? []).map((k) => t(`sellerSetup.docKind.${k}`)).join('، ') })}</Alert>
          ) : null}
          <div className="cluster" style={{ alignItems: 'flex-end' }}>
            <TextField label={t('sellerSetup.decisionNote')} optional maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} />
            {company.verification_status === 'PENDING' ? (
              <ApiActionButton size="sm" action={() => mp.decideCompanyVerification(company.id, 'VERIFIED', note)} onSuccess={onDone} onError={onError} leading={<Icon name="check" size={14} />}>
                {t('sellerSetup.verify')}
              </ApiActionButton>
            ) : null}
            <ApiActionButton size="sm" variant="ghost" action={() => mp.decideCompanyVerification(company.id, 'REJECTED', note || t('sellerSetup.rejectedNote'))} onSuccess={onDone} onError={onError}>
              {t('sellerSetup.reject')}
            </ApiActionButton>
            {company.verification_status === 'VERIFIED' ? (
              <ApiActionButton size="sm" variant="ghost" action={() => mp.decideCompanyVerification(company.id, 'SUSPENDED', note || t('sellerSetup.suspendedNote'))} onSuccess={onDone} onError={onError}>
                {t('sellerSetup.suspend')}
              </ApiActionButton>
            ) : null}
          </div>
        </>
      ) : null}
    </li>
  )
}

function DocumentList({ docs, onDone, onError }: { docs: SellerDocument[]; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const [note, setNote] = useState('')
  if (!docs.length) return <p className="text-caption">{t('sellerSetup.noDocuments')}</p>
  return (
    <div className="table-scroll">
      <table className="data-table" data-testid="admin-documents">
        <thead>
          <tr>
            <th scope="col">{t('sellerSetup.kind')}</th>
            <th scope="col">{t('sellerSetup.file')}</th>
            <th scope="col">{t('sellerSetup.status')}</th>
            <th scope="col"><span className="visually-hidden">{t('market.actions')}</span></th>
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id}>
              <td>{t(`sellerSetup.docKind.${d.kind}`)}{d.reference_number ? <div className="text-caption ltr">{d.reference_number}</div> : null}</td>
              <td>
                <button type="button" className="link-button" onClick={() => openPrivate(d.file_url).catch(onError)}>
                  <span className="ltr">{d.original_name}</span>
                </button>
                <div className="text-caption ltr">sha256 {d.sha256.slice(0, 12)}…</div>
              </td>
              <td><Badge tone={DOC_TONE[d.status]}>{t(`sellerSetup.docStatus.${d.status}`)}</Badge>{d.review_note ? <div className="text-caption">{d.review_note}</div> : null}</td>
              <td>
                {d.status === 'PENDING' ? (
                  <span className="cluster">
                    <ApiActionButton size="sm" action={() => mp.decideSellerDocument(d.id, true)} onSuccess={onDone} onError={onError}>{t('sellerSetup.approve')}</ApiActionButton>
                    <TextField label={t('sellerSetup.rejectReason')} optional maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} />
                    <ApiActionButton size="sm" variant="ghost" disabled={!note.trim()} action={() => mp.decideSellerDocument(d.id, false, note.trim())} onSuccess={onDone} onError={onError}>{t('sellerSetup.reject')}</ApiActionButton>
                  </span>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
