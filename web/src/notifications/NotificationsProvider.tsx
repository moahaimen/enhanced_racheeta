/**
 * Holds the unread-notification count for the signed-in account so the header badge
 * and the notification centre agree. The count is asked of the backend (never computed
 * locally) when an account signs in, on every authenticated SPA navigation (pathname
 * change) and after each mark-read action. There is no polling and no timer: a page that
 * stays open makes no periodic requests. It is cleared on logout.
 *
 * Races: each load aborts the previous one, logout/account switch/unmount abort the
 * current one, and a response is applied only while it is still the latest request for
 * the current account. A failed refresh keeps the last known value.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router'

import { notifications as notificationsApi } from '../api'
import { useAuth } from '../auth/useAuth'
import { NotificationsContext, type NotificationsContextValue } from './context'

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const { status, account } = useAuth()
  const { pathname } = useLocation()
  const accountId = status === 'authenticated' ? (account?.id ?? null) : null
  // The count is stored with the account it belongs to, so a stale value can never be shown
  // after logout or an account switch (derived below instead of reset in an effect).
  const [stored, setStored] = useState<{ accountId: string; count: number } | null>(null)
  const unreadCount = stored !== null && stored.accountId === accountId ? stored.count : null
  const latest = useRef(0)
  const controllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (accountId === null) return
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    const token = ++latest.current
    // Started inside a promise chain so a failing/absent loader can never throw during render.
    Promise.resolve()
      .then(() => notificationsApi.getUnreadCount(controller.signal))
      .then((result) => {
        if (!controller.signal.aborted && latest.current === token && typeof result?.count === 'number') {
          setStored({ accountId, count: result.count })
        }
      })
      .catch(() => {
        // A failed refresh must never break the page; the last known count stays.
      })
    return () => controller.abort()
    // `pathname` is the trigger: one count request per authenticated navigation.
  }, [accountId, pathname])

  const refreshUnreadCount = useCallback(async () => {
    if (accountId === null) return
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    const token = ++latest.current
    try {
      const result = await notificationsApi.getUnreadCount(controller.signal)
      if (!controller.signal.aborted && latest.current === token && typeof result?.count === 'number') {
        setStored({ accountId, count: result.count })
      }
    } catch {
      // Keep the last known value.
    }
  }, [accountId])

  // Abort whatever is in flight when the provider goes away.
  useEffect(() => () => controllerRef.current?.abort(), [])

  const value = useMemo<NotificationsContextValue>(
    () => ({ unreadCount, refreshUnreadCount }),
    [unreadCount, refreshUnreadCount],
  )
  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>
}
