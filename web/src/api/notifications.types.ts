import type { Paginated } from './providers.types'

export type NotificationCategory = 'RESERVATION'
export type NotificationEventType = 'RESERVATION_CREATED' | 'RESERVATION_STATUS_CHANGED'

/** One persistent notification. `title`/`body` are rendered by the backend in the request language. */
export interface AppNotification {
  id: string
  category: NotificationCategory
  event_type: NotificationEventType
  title: string
  body: string
  /** Open-ended on purpose: unknown future kinds must render without a link, not break. */
  resource_type: string
  resource_id: string | null
  is_read: boolean
  read_at: string | null
  created_at: string
}

export type PaginatedNotifications = Paginated<AppNotification>

export interface UnreadCount {
  count: number
}

export interface MarkAllReadResult {
  updated: number
}
