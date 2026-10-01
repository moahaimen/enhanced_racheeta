import { createContext } from 'react'

export interface NotificationsContextValue {
  /** Server-reported unread count; null until the first answer (or when it cannot be loaded). */
  unreadCount: number | null
  /** Re-ask the backend. The count is never computed or adjusted locally. */
  refreshUnreadCount: () => Promise<void>
}

export const NotificationsContext = createContext<NotificationsContextValue | null>(null)
