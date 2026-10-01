/**
 * Holds the unread-notification count for the signed-in account so the header badge
 * and the notification centre agree. One `GET /notifications/unread-count/` on login
 * and after each mark-read action; no polling, no timers, no full-list fetch. The value
 * is always what the backend last said, and is cleared on logout.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { notifications as notificationsApi } from '../api'
import { useAuth } from '../auth/useAuth'
import { NotificationsContext, type NotificationsContextValue } from './context'

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const { status, account } = useAuth()
  const accountId = status === 'authenticated' ? (account?.id ?? null) : null
  // The count is stored with the account it belongs to, so a stale value can never be shown
  // after logout or an account switch (derived below instead of reset in an effect).
  const [stored, setStored] = useState<{ accountId: string; count: number } | null>(null)
  const unreadCount = stored !== null && stored.accountId === accountId ? stored.count : null
  // A response is applied only while it is still the latest request for the current account.
  const latest = useRef(0)

  useEffect(() => {
    if (accountId === null) return
    let active = true
    const token = ++latest.current
    // Started inside a promise chain so a failing/absent loader can never throw during render.
    Promise.resolve()
      .then(() => notificationsApi.getUnreadCount())
      .then((result) => {
        if (active && latest.current === token && typeof result?.count === 'number') {
          setStored({ accountId, count: result.count })
        }
      })
      .catch(() => {
        // A failed count must never break the page; the badge simply stays hidden.
      })
    return () => {
      active = false
    }
  }, [accountId])

  const refreshUnreadCount = useCallback(async () => {
    if (accountId === null) return
    const token = ++latest.current
    try {
      const result = await notificationsApi.getUnreadCount()
      if (latest.current === token && typeof result?.count === 'number') {
        setStored({ accountId, count: result.count })
      }
    } catch {
      // Keep the last known value.
    }
  }, [accountId])

  const value = useMemo<NotificationsContextValue>(
    () => ({ unreadCount, refreshUnreadCount }),
    [unreadCount, refreshUnreadCount],
  )
  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>
}
