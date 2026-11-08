import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'

import { realEstate as realEstateApi } from '../../api'
import type { InquiryStatus, ListingInquiry } from '../../api'
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
  Pagination,
} from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import { inquiryTone } from './inquiryTone'

const PAGE_SIZE = 20
const LIVE: InquiryStatus[] = ['OPEN', 'ANSWERED']

/** /real-estate/inquiries — the signed-in account's own inquiries (any role can ask). */
export function MyInquiriesPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  return (
    <Container width="lg">
      <PageHeader
        eyebrow={<><Icon name="home" size={16} />{t('modules.realEstate')}</>}
        title={t('inquiries.myTitle')}
        description={t('inquiries.myIntro')}
      />
      <PageStack>
        <AsyncPage load={(signal) => realEstateApi.listMyInquiries(page, signal)} deps={[page]}>
          {(result, reload) =>
            result.results.length === 0 ? (
              <div className="card-block">
                <EmptyState
                  icon="home"
                  title={t('inquiries.empty')}
                  action={<LinkButton to="/real-estate">{t('inquiries.browse')}</LinkButton>}
                  testId="my-inquiries-empty"
                />
              </div>
            ) : (
              <>
                <ul className="stack" style={{ listStyle: 'none', padding: 0, margin: 0 }} data-testid="my-inquiries">
                  {result.results.map((inquiry) => (
                    <MyInquiry key={inquiry.id} inquiry={inquiry} reload={reload} />
                  ))}
                </ul>
                <Pagination
                  page={page}
                  total={Math.max(1, Math.ceil(result.count / PAGE_SIZE))}
                  hasNext={result.next !== null}
                  hasPrevious={result.previous !== null}
                  onChange={(next) => setParams(next > 1 ? { page: String(next) } : {})}
                />
              </>
            )
          }
        </AsyncPage>
      </PageStack>
    </Container>
  )
}

function MyInquiry({ inquiry, reload }: { inquiry: ListingInquiry; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  return (
    <li className="card-block stack-sm" data-testid="my-inquiry">
      <div className="cluster" style={{ justifyContent: 'space-between' }}>
        <strong>
          {inquiry.listing_is_public ? (
            <Link to={`/real-estate/${inquiry.listing_id}`}>{inquiry.listing_title_snapshot}</Link>
          ) : (
            inquiry.listing_title_snapshot
          )}
        </strong>
        <Badge tone={inquiryTone(inquiry.status)}>{t(`inquiries.status.${inquiry.status}`)}</Badge>
      </div>
      {!inquiry.listing_is_public ? <p className="text-caption">{t('inquiries.listingGone')}</p> : null}
      <p className="text-caption">{t('inquiries.sentOn', { date: new Date(inquiry.created_at).toLocaleDateString(i18n.language) })}</p>
      <p className="prewrap" dir="auto">{inquiry.message}</p>
      {inquiry.owner_response ? (
        <div className="card-block" data-testid="owner-response">
          <strong>{t('inquiries.response')}</strong>
          <p className="prewrap" dir="auto">{inquiry.owner_response}</p>
        </div>
      ) : null}
      {error ? <Alert kind="error">{error}</Alert> : null}
      {LIVE.includes(inquiry.status) ? (
        <div className="cluster">
          <ApiActionButton
            size="sm"
            variant="ghost"
            action={() => realEstateApi.withdrawMyInquiry(inquiry.id)}
            onSuccess={() => {
              setError(null)
              reload()
            }}
            onError={(err) => setError(toErrorMessage(err))}
          >
            {t('inquiries.withdraw')}
          </ApiActionButton>
        </div>
      ) : null}
    </li>
  )
}
