import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiRequest } from '../client'

vi.mock('../client', () => ({ apiRequest: vi.fn().mockResolvedValue({}) }))

const real = await vi.importActual<typeof import('./chat')>('./chat')
const calls = () => vi.mocked(apiRequest).mock.calls

describe('chat endpoints', () => {
  beforeEach(() => vi.mocked(apiRequest).mockClear())

  it('opens reservation conversations without client participant data', async () => {
    await real.openReservationConversation('reservation id')
    expect(calls()[0]).toEqual([
      '/api/v1/chat/reservations/reservation%20id/conversation',
      { method: 'POST' },
    ])
  })

  it('lists conversations and messages with page queries', async () => {
    await real.listConversations()
    await real.listConversations(2)
    await real.listMessages('conversation', 3)
    expect(calls()[0]?.[0]).toBe('/api/v1/chat/conversations/')
    expect(calls()[1]?.[0]).toBe('/api/v1/chat/conversations/?page=2')
    expect(calls()[2]?.[0]).toBe('/api/v1/chat/conversations/conversation/messages/?page=3')
  })

  it('sends only body and marks read without a body', async () => {
    await real.sendMessage('abc', 'hello')
    await real.markRead('abc', 7)
    expect(calls()[0]).toEqual([
      '/api/v1/chat/conversations/abc/messages/',
      { method: 'POST', body: { body: 'hello' } },
    ])
    expect(calls()[1]).toEqual([
      '/api/v1/chat/conversations/abc/read/',
      { method: 'POST', body: { through_sequence: 7 } },
    ])
  })

  it('reads backend unread count', async () => {
    await real.getUnreadCount()
    expect(calls()[0]?.[0]).toBe('/api/v1/chat/unread-count/')
  })
})
