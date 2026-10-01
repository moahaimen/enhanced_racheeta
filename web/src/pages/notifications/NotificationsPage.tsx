import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { notifications as notificationsApi } from '../../api'
import type { AppNotification } from '../../api'
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
import { useAuth } from '../../auth/useAuth'
import { toErrorMessage } from '../../hooks/useAsync'
import { useNotifications } from '../../notifications/useNotifications'
import { notificationTarget } from './target'
import styles from './NotificationsPage.module.css'

const PAGE_SIZE = 20

export function NotificationsPage() {
  const { t } = useTranslation()
  const { unreadCount, refreshUnreadCount } = useNotifications()
  const [params, setParams] = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const goTo = (next: number) => setParams(next > 1 ? { page: String(next) } : {})

  return (
    <Container width="xl">
      <PageHeader
        eyebrow={<><Icon name="bell" size={16} />{t('nav.notifications')}</>}
        title={t('notifications.title')}
        description={t('notifications.intro')}
      />
      <PageStack>
        {error ? <Alert kind="error">{error}</Alert> : null}
        <AsyncPage load={(signal) => notificationsApi.listNotifications(page, signal)} deps={[page]}>
          {(result, reload) => {
            const afterChange = () => {
              setError(null)
              reload()
              void refreshUnreadCount()
            }
            return result.results.length === 0 ? (
              <div className="card-block">
                <EmptyState
                  icon="bell"
                  title={page > 1 ? t('notifications.emptyPage') : t('notifications.empty')}
                />
              </div>
            ) : (
              <>
                <div className={styles.footer}>
                  <p className="text-caption">{t('notifications.count', { count: result.count })}</p>
                  <ApiActionButton
                    variant="secondary"
                    size="sm"
                    disabled={unreadCount === 0}
                    action={() => notificationsApi.markAllRead()}
                    onSuccess={afterChange}
                    onError={(err) => setError(toErrorMessage(err))}
                    pendingLabel={t('notifications.markingAll')}
                    leading={<Icon name="check" size={16} />}
                  >
                    {t('notifications.markAllRead')}
                  </ApiActionButton>
                </div>
                <ul className={styles.list}>
                  {result.results.map((notification) => (
                    <NotificationRow
                      key={notification.id}
                      notification={notification}
                      onChanged={afterChange}
                      onError={(err) => setError(toErrorMessage(err))}
                    />
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
          }}
        </AsyncPage>
      </PageStack>
    </Container>
  )
}

function NotificationRow({
  notification,
  onChanged,
  onError,
}: {
  notification: AppNotification
  onChanged: () => void
  onError: (error: unknown) => void
}) {
  const { t, i18n } = useTranslation()
  const { account } = useAuth()
  const target = notificationTarget(notification, account?.role)
  return (
    <li
      className={`${styles.item} ${notification.is_read ? '' : styles.unread}`.trim()}
      data-read={notification.is_read ? 'true' : 'false'}
    >
      <div className={styles.head}>
        <h2 className={styles.title}>{notification.title}</h2>
        {notification.is_read ? (
          <Badge tone="neutral">{t('notifications.read')}</Badge>
        ) : (
          <Badge tone="brand">{t('notifications.unread')}</Badge>
        )}
      </div>
      {notification.body ? <p className={styles.body}>{notification.body}</p> : null}
      <div className={styles.footer}>
        <time className="text-caption" dateTime={notification.created_at}>
          {new Date(notification.created_at).toLocaleString(i18n.language)}
        </time>
        <div className={styles.actions}>
          {target ? (
            <LinkButton to={target} variant="ghost" size="sm">
              {t('notifications.view')}
            </LinkButton>
          ) : null}
          {notification.is_read ? null : (
            <ApiActionButton
              variant="ghost"
              size="sm"
              action={() => notificationsApi.markRead(notification.id)}
              onSuccess={onChanged}
              onError={onError}
              pendingLabel={t('notifications.marking')}
            >
              {t('notifications.markRead')}
            </ApiActionButton>
          )}
        </div>
      </div>
    </li>
  )
}
