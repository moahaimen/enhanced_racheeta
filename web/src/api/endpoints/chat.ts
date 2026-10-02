import { apiRequest } from '../client'
import type {
  ChatMessage,
  ChatReadState,
  ChatUnreadCount,
  Conversation,
  PaginatedChatMessages,
  PaginatedConversations,
} from '../chat.types'

export function openReservationConversation(reservationId: string): Promise<Conversation> {
  return apiRequest<Conversation>(
    `/api/v1/chat/reservations/${encodeURIComponent(reservationId)}/conversation`,
    { method: 'POST' },
  )
}

export function listConversations(
  page = 1,
  signal?: AbortSignal,
): Promise<PaginatedConversations> {
  const query = page > 1 ? `?page=${page}` : ''
  return apiRequest<PaginatedConversations>(`/api/v1/chat/conversations/${query}`, {
    signal,
  })
}

export function listMessages(
  conversationId: string,
  page = 1,
  signal?: AbortSignal,
): Promise<PaginatedChatMessages> {
  const query = page > 1 ? `?page=${page}` : ''
  return apiRequest<PaginatedChatMessages>(
    `/api/v1/chat/conversations/${encodeURIComponent(conversationId)}/messages/${query}`,
    { signal },
  )
}

export function sendMessage(conversationId: string, body: string): Promise<ChatMessage> {
  return apiRequest<ChatMessage>(
    `/api/v1/chat/conversations/${encodeURIComponent(conversationId)}/messages/`,
    { method: 'POST', body: { body } },
  )
}

export function markRead(conversationId: string): Promise<ChatReadState> {
  return apiRequest<ChatReadState>(
    `/api/v1/chat/conversations/${encodeURIComponent(conversationId)}/read/`,
    { method: 'POST' },
  )
}

export function getUnreadCount(signal?: AbortSignal): Promise<ChatUnreadCount> {
  return apiRequest<ChatUnreadCount>('/api/v1/chat/unread-count/', { signal })
}
