import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { realEstate as realEstateApi } from '../../api'
import { INQUIRY_STATUSES, type InquiryStatus, type OwnerInquiry } from '../../api'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Badge,
  Container,
  EmptyState,
  FormActions,
  Icon,
  PageHeader,
  PageStack,
  Pagination,
  Select,
  Textarea,
} from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import { inquiryTone } from './inquiryTone'

const PAGE_SIZE = 20

/** /real-estate/owner/inquiries — inquiries about the signed-in seller's own listings. */
export function OwnerInquiriesPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const raw = params.get('status') ?? ''
  const status = (INQUIRY_STATUSES as readonly string[]).includes(raw) ? (raw as InquiryStatus) : ''
  const update = (next: { status?: string; page?: number }) => {
    const q = new URLSearchParams()
    const s = next.status ?? status
    const p = next.page ?? 1
    if (s) q.set('status', s)
    if (p > 1) q.set('page', String(p))
    setParams(q)
  }
  return (
    <Container width="lg">
      <PageHeader
        eyebrow={<><Icon name="home" size={16} />{t('nav.realEstateWorkspace')}</>}
        title={t('inquiries.ownerTitle')}
        description={t('inquiries.ownerIntro')}
      />
      <PageStack>
        <div style={{ maxWidth: 260 }}>
          <Select label={t('inquiries.statusFilter')} value={status} onChange={(event) => update({ status: event.target.value })}>
            <option value="">{t('inquiries.allStatuses')}</option>
            {INQUIRY_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`inquiries.status.${s}`)}
              </option>
            ))}
          </Select>
        </div>
        <AsyncPage load={(signal) => realEstateApi.listOwnerInquiries({ status, page }, signal)} deps={[status, page]}>
          {(result, reload) =>
            result.results.length === 0 ? (
              <div className="card-block">
                <EmptyState icon="mail" title={t('inquiries.ownerEmpty')} testId="owner-inquiries-empty" />
              </div>
            ) : (
              <>
                <ul className="stack" style={{ listStyle: 'none', padding: 0, margin: 0 }} data-testid="owner-inquiries">
                  {result.results.map((inquiry) => (
                    <OwnerInquiryRow key={inquiry.id} inquiry={inquiry} reload={reload} />
                  ))}
                </ul>
                <Pagination
                  page={page}
                  total={Math.max(1, Math.ceil(result.count / PAGE_SIZE))}
                  hasNext={result.next !== null}
                  hasPrevious={result.previous !== null}
                  onChange={(next) => update({ page: next })}
                />
              </>
            )
          }
        </AsyncPage>
      </PageStack>
    </Container>
  )
}

function OwnerInquiryRow({ inquiry, reload }: { inquiry: OwnerInquiry; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const [answer, setAnswer] = useState('')
  const [error, setError] = useState<string | null>(null)
  const live = inquiry.status === 'OPEN' || inquiry.status === 'ANSWERED'
  const done = () => {
    setError(null)
    setAnswer('')
    reload()
  }
  return (
    <li className="card-block stack-sm" data-testid="owner-inquiry">
      <div className="cluster" style={{ justifyContent: 'space-between' }}>
        <strong>{inquiry.listing_title_snapshot}</strong>
        <Badge tone={inquiryTone(inquiry.status)}>{t(`inquiries.status.${inquiry.status}`)}</Badge>
      </div>
      <p className="text-caption">
        {t('inquiries.from')}: {inquiry.inquirer.full_name} ·{' '}
        {t('inquiries.sentOn', { date: new Date(inquiry.created_at).toLocaleDateString(i18n.language) })}
      </p>
      {inquiry.share_contact ? (
        <p dir="ltr" className="cluster" data-testid="inquirer-contact">
          <Badge tone="outline">{t('inquiries.contactShared')}</Badge>
          {inquiry.inquirer.phone_number ? <span><Icon name="phone" size={14} /> {inquiry.inquirer.phone_number}</span> : null}
          {inquiry.inquirer.email ? <span><Icon name="mail" size={14} /> {inquiry.inquirer.email}</span> : null}
        </p>
      ) : (
        <p className="text-caption">{t('inquiries.contactPrivate')}</p>
      )}
      <p className="prewrap" dir="auto">{inquiry.message}</p>
      {inquiry.owner_response ? (
        <div className="card-block">
          <strong>{t('inquiries.response')}</strong>
          <p className="prewrap" dir="auto">{inquiry.owner_response}</p>
        </div>
      ) : null}
      {error ? <Alert kind="error">{error}</Alert> : null}
      {live ? (
        <>
          <Textarea label={t('inquiries.yourAnswer')} rows={3} maxLength={1000} value={answer} onChange={(event) => setAnswer(event.target.value)} />
          <FormActions>
            <ApiActionButton
              size="sm"
              disabled={answer.trim().length < 2}
              action={() => realEstateApi.respondToInquiry(inquiry.id, answer.trim())}
              onSuccess={done}
              onError={(err) => setError(toErrorMessage(err))}
            >
              {inquiry.status === 'ANSWERED' ? t('inquiries.answerAgain') : t('inquiries.answer')}
            </ApiActionButton>
            <ApiActionButton
              size="sm"
              variant="ghost"
              action={() => realEstateApi.closeInquiry(inquiry.id)}
              onSuccess={done}
              onError={(err) => setError(toErrorMessage(err))}
            >
              {t('inquiries.close')}
            </ApiActionButton>
          </FormActions>
        </>
      ) : null}
    </li>
  )
}
