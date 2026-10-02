import { createContext } from 'react'

export interface ChatContextValue {
  unreadCount: number | null
  refreshUnreadCount: () => Promise<void>
}

export const ChatContext = createContext<ChatContextValue | null>(null)
