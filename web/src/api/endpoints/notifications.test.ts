import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiRequest } from '../client'

vi.mock('../client', () => ({ apiRequest: vi.fn().mockResolvedValue({}) }))

// The test setup replaces the endpoint module with a stub; load the real one here.
const real = await vi.importActual<typeof import('./notifications')>('./notifications')

const calls = () => vi.mocked(apiRequest).mock.calls

describe('notification endpoints', () => {
  beforeEach(() => vi.mocked(apiRequest).mockClear())

  it('lists with the page query only beyond page one', async () => {
    await real.listNotifications()
    await real.listNotifications(3)
    expect(calls()[0]?.[0]).toBe('/api/v1/notifications/')
    expect(calls()[1]?.[0]).toBe('/api/v1/notifications/?page=3')
  })

  it('reads the unread count', async () => {
    await real.getUnreadCount()
    expect(calls()[0]?.[0]).toBe('/api/v1/notifications/unread-count/')
  })

  it('posts mark-read and read-all without any client data', async () => {
    await real.markRead('abc')
    await real.markAllRead()
    expect(calls()[0]).toEqual(['/api/v1/notifications/abc/read/', { method: 'POST' }])
    expect(calls()[1]).toEqual(['/api/v1/notifications/read-all/', { method: 'POST' }])
  })
})
