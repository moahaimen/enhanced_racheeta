import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { chat as chatApi } from '../../api'
import {
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
import styles from './MessagesPage.module.css'

const PAGE_SIZE = 20

export function MessagesPage() {
  const { t, i18n } = useTranslation()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const goTo = (next: number) => setParams(next > 1 ? { page: String(next) } : {})

  return (
    <Container width="xl">
      <PageHeader
        eyebrow={<><Icon name="mail" size={16} />{t('nav.messages')}</>}
        title={t('messages.title')}
        description={t('messages.intro')}
      />
      <PageStack>
        <AsyncPage load={(signal) => chatApi.listConversations(page, signal)} deps={[page]}>
          {(result) =>
            result.results.length === 0 ? (
              <div className="card-block">
                <EmptyState
                  icon="mail"
                  title={page > 1 ? t('messages.emptyPage') : t('messages.empty')}
                />
              </div>
            ) : (
              <>
                <p className="text-caption">{t('messages.count', { count: result.count })}</p>
                <ul className={styles.list}>
                  {result.results.map((conversation) => (
                    <li
                      key={conversation.id}
                      className={`${styles.item} ${
                        conversation.unread_count > 0 ? styles.itemUnread : ''
                      }`.trim()}
                    >
                      <div className={styles.row}>
                        <div>
                          <strong>
                            {conversation.other_participant?.full_name ?? t('messages.participant')}
                          </strong>
                          <div className={styles.meta}>{t('messages.reservationConversation')}</div>
                        </div>
                        {conversation.unread_count > 0 ? (
                          <Badge tone="brand">
                            {t('messages.unreadCount', { count: conversation.unread_count })}
                          </Badge>
                        ) : null}
                      </div>
                      {conversation.last_message_at ? (
                        <time className={styles.meta} dateTime={conversation.last_message_at}>
                          {new Date(conversation.last_message_at).toLocaleString(i18n.language)}
                        </time>
                      ) : (
                        <span className={styles.meta}>{t('messages.noMessagesYet')}</span>
                      )}
                      <div>
                        <LinkButton to={`/messages/${conversation.id}`} size="sm">
                          {t('messages.open')}
                        </LinkButton>
                      </div>
                    </li>
                  ))}
                </ul>
                <Pagination
                  page={page}
                  total={Math.max(1, Math.ceil(result.count / PAGE_SIZE))}
                  hasNext={result.next !== null}
                  hasPrevious={result.previous !== null}
                  onChange={goTo}
                />
              </>
            )
          }
        </AsyncPage>
      </PageStack>
    </Container>
  )
}
