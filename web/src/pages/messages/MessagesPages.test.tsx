import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../../api/endpoints/auth'
import * as chatApi from '../../api/endpoints/chat'
import { tokenStore } from '../../api/tokens'
import type { ChatMessage, Conversation } from '../../api'
import { makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')

const conversation: Conversation = {
  id: '11111111-1111-4111-8111-111111111111',
  context_type: 'RESERVATION',
  context_id: '22222222-2222-4222-8222-222222222222',
  other_participant: {
    id: '33333333-3333-4333-8333-333333333333',
    full_name: 'Dr Chat',
    role: 'PROVIDER',
  },
  last_sequence: 1,
  last_read_sequence: 0,
  unread_count: 1,
  last_message_at: '2026-10-02T08:00:00Z',
  created_at: '2026-10-02T07:00:00Z',
}

const message: ChatMessage = {
  id: '44444444-4444-4444-8444-444444444444',
  sequence: 1,
  sender: conversation.other_participant!,
  is_mine: false,
  body: 'Hello from provider',
  created_at: '2026-10-02T08:00:00Z',
}

describe('chat pages', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PATIENT' }))
    vi.mocked(chatApi.getUnreadCount).mockResolvedValue({ count: 1 })
    vi.mocked(chatApi.markRead).mockResolvedValue({ last_read_sequence: 1 })
  })

  it('lists my conversations with backend unread state', async () => {
    vi.mocked(chatApi.listConversations).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [conversation],
    })

    renderApp('/messages')

    expect(await screen.findByText('Dr Chat')).toBeInTheDocument()
    expect(screen.getByText(/1.*غير مقروء|1.*unread/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /فتح المحادثة|open conversation/i })).toHaveAttribute(
      'href',
      `/messages/${conversation.id}`,
    )
  })

  it('marks a thread read and sends an immutable text message', async () => {
    vi.mocked(chatApi.listMessages)
      .mockResolvedValueOnce({
        count: 1,
        next: null,
        previous: null,
        results: [message],
      })
      .mockResolvedValue({
        count: 2,
        next: null,
        previous: null,
        results: [
          message,
          {
            ...message,
            id: '55555555-5555-4555-8555-555555555555',
            sequence: 2,
            is_mine: true,
            body: 'My reply',
          },
        ],
      })
    vi.mocked(chatApi.sendMessage).mockResolvedValue({
      ...message,
      id: '55555555-5555-4555-8555-555555555555',
      sequence: 2,
      is_mine: true,
      body: 'My reply',
    })

    renderApp(`/messages/${conversation.id}`)

    expect(await screen.findByText('Hello from provider')).toBeInTheDocument()
    await waitFor(() => expect(chatApi.markRead).toHaveBeenCalledWith(conversation.id))

    const box = screen.getByLabelText(/الرسالة|message/i)
    await userEvent.type(box, 'My reply')
    await userEvent.click(screen.getByRole('button', { name: /^إرسال$|^send$/i }))

    await waitFor(() =>
      expect(chatApi.sendMessage).toHaveBeenCalledWith(conversation.id, 'My reply'),
    )
    expect(await screen.findByText('My reply')).toBeInTheDocument()
  })
})
