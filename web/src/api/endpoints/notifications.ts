import { apiRequest } from '../client'
import type {
  AppNotification,
  MarkAllReadResult,
  PaginatedNotifications,
  UnreadCount,
} from '../notifications.types'

export function listNotifications(page = 1, signal?: AbortSignal): Promise<PaginatedNotifications> {
  const query = page > 1 ? `?page=${page}` : ''
  return apiRequest<PaginatedNotifications>(`/api/v1/notifications/${query}`, { signal })
}

export function getUnreadCount(signal?: AbortSignal): Promise<UnreadCount> {
  return apiRequest<UnreadCount>('/api/v1/notifications/unread-count/', { signal })
}

/** The backend owns the timestamp: no body is sent. */
export function markRead(id: string): Promise<AppNotification> {
  return apiRequest<AppNotification>(`/api/v1/notifications/${encodeURIComponent(id)}/read/`, {
    method: 'POST',
  })
}

export function markAllRead(): Promise<MarkAllReadResult> {
  return apiRequest<MarkAllReadResult>('/api/v1/notifications/read-all/', { method: 'POST' })
}
