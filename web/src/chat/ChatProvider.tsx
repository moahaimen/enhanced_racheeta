import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router'

import { chat as chatApi } from '../api'
import { useAuth } from '../auth/useAuth'
import { ChatContext, type ChatContextValue } from './context'

export function ChatProvider({ children }: { children: ReactNode }) {
  const { status, account } = useAuth()
  const { pathname } = useLocation()
  const accountId = status === 'authenticated' ? (account?.id ?? null) : null
  const [stored, setStored] = useState<{ accountId: string; count: number } | null>(null)
  const unreadCount = stored !== null && stored.accountId === accountId ? stored.count : null
  const latest = useRef(0)
  const controllerRef = useRef<AbortController | null>(null)

  const refreshUnreadCount = useCallback(async () => {
    if (accountId === null) return
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    const token = ++latest.current
    try {
      const result = await chatApi.getUnreadCount(controller.signal)
      if (!controller.signal.aborted && latest.current === token) {
        setStored({ accountId, count: result.count })
      }
    } catch {
      // Chat count failure never breaks application navigation.
    }
  }, [accountId])

  useEffect(() => {
    void refreshUnreadCount()
    return () => controllerRef.current?.abort()
  }, [refreshUnreadCount, pathname])

  useEffect(() => () => controllerRef.current?.abort(), [])

  const value = useMemo<ChatContextValue>(
    () => ({ unreadCount, refreshUnreadCount }),
    [unreadCount, refreshUnreadCount],
  )
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}
