import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// The header asks the backend for the unread count once an account is signed in. Tests
// that exercise other pages must not hit the network; notification tests override this.
vi.mock('../api/endpoints/chat', () => ({
  openReservationConversation: vi.fn(),
  listConversations: vi.fn(),
  listMessages: vi.fn(),
  sendMessage: vi.fn(),
  markRead: vi.fn().mockResolvedValue({ last_read_sequence: 0 }),
  getUnreadCount: vi.fn().mockResolvedValue({ count: 0 }),
}))

vi.mock('../api/endpoints/notifications', () => ({
  listNotifications: vi.fn(),
  getUnreadCount: vi.fn().mockResolvedValue({ count: 0 }),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
}))

afterEach(() => {
  cleanup()
  window.localStorage.clear()
})
