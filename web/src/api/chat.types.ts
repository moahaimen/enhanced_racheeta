import type { Paginated } from './providers.types'

export type ConversationContextType = 'RESERVATION'

export interface ChatAccount {
  id: string
  full_name: string
  role: string
}

export interface Conversation {
  id: string
  context_type: ConversationContextType
  context_id: string
  other_participant: ChatAccount | null
  last_sequence: number
  last_read_sequence: number
  unread_count: number
  last_message_at: string | null
  created_at: string
}

export interface ChatMessage {
  id: string
  sequence: number
  sender: ChatAccount
  is_mine: boolean
  body: string
  created_at: string
}

export interface ChatUnreadCount {
  count: number
}

export interface ChatReadState {
  last_read_sequence: number
}

export type PaginatedConversations = Paginated<Conversation>
export type PaginatedChatMessages = Paginated<ChatMessage>
