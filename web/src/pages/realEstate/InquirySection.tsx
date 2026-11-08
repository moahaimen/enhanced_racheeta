import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { realEstate as realEstateApi } from '../../api'
import { useAuth } from '../../auth/useAuth'
import { Alert, ApiActionButton, Checkbox, FormActions, LinkButton, SectionCard, Textarea } from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'

const MIN = 10
const MAX = 1000

/** "Ask the owner" on a public listing. The backend decides everything (visibility, own listing,
 * duplicates, daily cap, throttle) and answers with typed codes shown as localized messages. */
export function InquirySection({ listingId }: { listingId: string }) {
  const { t } = useTranslation()
  const { status } = useAuth()
  const [message, setMessage] = useState('')
  const [share, setShare] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const length = message.trim().length

  return (
    <SectionCard title={t('inquiries.title')} description={t('inquiries.intro')} headingLevel={2}>
      {status !== 'authenticated' ? (
        <LinkButton to="/login" variant="secondary">
          {t('inquiries.loginToAsk')}
        </LinkButton>
      ) : sent ? (
        <Alert kind="success" testId="inquiry-sent">
          {t('inquiries.sent')}{' '}
          <LinkButton to="/real-estate/inquiries" variant="ghost" size="sm">
            {t('nav.myPropertyInquiries')}
          </LinkButton>
        </Alert>
      ) : (
        <div className="stack" data-testid="inquiry-form">
          {error ? <Alert kind="error">{error}</Alert> : null}
          <Textarea
            label={t('inquiries.message')}
            hint={t('inquiries.messageHint')}
            rows={4}
            maxLength={MAX}
            value={message}
            onChange={(event) => setMessage(event.target.value)}
          />
          <Checkbox label={t('inquiries.shareContact')} checked={share} onChange={(event) => setShare(event.target.checked)} />
          <FormActions>
            <ApiActionButton
              disabled={length < MIN}
              action={() => realEstateApi.sendInquiry(listingId, message.trim(), share)}
              onSuccess={() => {
                setError(null)
                setSent(true)
              }}
              onError={(err) => setError(toErrorMessage(err))}
              pendingLabel={t('inquiries.sending')}
            >
              {t('inquiries.send')}
            </ApiActionButton>
          </FormActions>
        </div>
      )}
    </SectionCard>
  )
}
