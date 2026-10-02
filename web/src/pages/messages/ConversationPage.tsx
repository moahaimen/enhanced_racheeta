import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, useSearchParams } from 'react-router'

import { chat as chatApi } from '../../api'
import { useChat } from '../../chat/useChat'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Container,
  EmptyState,
  Icon,
  LinkButton,
  PageHeader,
  PageStack,
  Pagination,
  Textarea,
} from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import styles from './MessagesPage.module.css'

const PAGE_SIZE = 20

export function ConversationPage() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation()
  const { refreshUnreadCount } = useChat()
  const [params, setParams] = useSearchParams()
  const [body, setBody] = useState('')
  const [error, setError] = useState<string | null>(null)
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const goTo = (next: number) => setParams(next > 1 ? { page: String(next) } : {})

  useEffect(() => {
    if (!id) return
    let active = true
    chatApi
      .markRead(id)
      .then(() => {
        if (active) void refreshUnreadCount()
      })
      .catch(() => {
        // AsyncPage owns the participant/not-found error presentation.
      })
    return () => {
      active = false
    }
  }, [id, refreshUnreadCount])

  return (
    <Container width="xl">
      <PageHeader
        eyebrow={<><Icon name="mail" size={16} />{t('nav.messages')}</>}
        title={t('messages.threadTitle')}
        description={t('messages.threadIntro')}
        actions={
          <LinkButton to="/messages" variant="secondary">
            {t('messages.back')}
          </LinkButton>
        }
      />
      <PageStack>
        {error ? <Alert kind="error">{error}</Alert> : null}
        <AsyncPage load={(signal) => chatApi.listMessages(id, page, signal)} deps={[id, page]}>
          {(result, reload) => (
            <div className={styles.thread}>
              {result.results.length === 0 ? (
                <EmptyState icon="mail" title={t('messages.noMessagesYet')} />
              ) : (
                <ul className={styles.messages}>
                  {result.results.map((message) => (
                    <li
                      key={message.id}
                      className={`${styles.message} ${message.is_mine ? styles.mine : ''}`.trim()}
                    >
                      <div className={styles.messageHead}>
                        <strong>
                          {message.is_mine ? t('messages.you') : message.sender.full_name}
                        </strong>
                        <time dateTime={message.created_at}>
                          {new Date(message.created_at).toLocaleString(i18n.language)}
                        </time>
                      </div>
                      <p className={styles.body}>{message.body}</p>
                    </li>
                  ))}
                </ul>
              )}
              <Pagination
                page={page}
                total={Math.max(1, Math.ceil(result.count / PAGE_SIZE))}
                hasNext={result.next !== null}
                hasPrevious={result.previous !== null}
                onChange={goTo}
              />
              {page === 1 ? (
                <div className={styles.composer}>
                  <Textarea
                    label={t('messages.message')}
                    value={body}
                    rows={3}
                    maxLength={2000}
                    onChange={(event) => setBody(event.target.value)}
                    placeholder={t('messages.placeholder')}
                  />
                  <div>
                    <ApiActionButton
                      action={() => chatApi.sendMessage(id, body)}
                      disabled={!body.trim()}
                      onSuccess={() => {
                        setBody('')
                        setError(null)
                        reload()
                        void chatApi.markRead(id).then(refreshUnreadCount)
                      }}
                      onError={(err) => setError(toErrorMessage(err))}
                      pendingLabel={t('messages.sending')}
                      leading={<Icon name="mail" size={16} />}
                    >
                      {t('messages.send')}
                    </ApiActionButton>
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </AsyncPage>
      </PageStack>
    </Container>
  )
}
