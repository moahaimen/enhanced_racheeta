import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../../api/endpoints/auth'
import * as notificationsApi from '../../api/endpoints/notifications'
import { tokenStore } from '../../api/tokens'
import { ApiError } from '../../api'
import type { AppNotification, PaginatedNotifications } from '../../api'
import { changeLanguage } from '../../i18n'
import { deferred, makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')

function note(overrides: Partial<AppNotification> = {}): AppNotification {
  return {
    id: '10000000-0000-4000-8000-000000000001',
    category: 'RESERVATION',
    event_type: 'RESERVATION_STATUS_CHANGED',
    title: 'Reservation confirmed',
    body: 'The reservation for "Consultation" with Dr Notify is now confirmed.',
    resource_type: 'RESERVATION',
    resource_id: '20000000-0000-4000-8000-000000000001',
    is_read: false,
    read_at: null,
    created_at: '2026-09-30T10:00:00Z',
    ...overrides,
  }
}

function pageOf(results: AppNotification[], extra: Partial<PaginatedNotifications> = {}): PaginatedNotifications {
  return { count: results.length, next: null, previous: null, results, ...extra }
}

const unread = note()
const read = note({
  id: '10000000-0000-4000-8000-000000000002',
  title: 'Reservation rejected',
  is_read: true,
  read_at: '2026-09-30T11:00:00Z',
})

describe('NotificationsPage', () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    await changeLanguage('en')
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PATIENT' }))
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 1 })
  })

  it('shows a loading state, then the notifications', async () => {
    const pending = deferred<PaginatedNotifications>()
    vi.mocked(notificationsApi.listNotifications).mockReturnValue(pending.promise)
    renderApp('/notifications')

    expect(await screen.findByTestId('async-loading')).toBeInTheDocument()
    pending.resolve(pageOf([unread]))
    expect(await screen.findByText('Reservation confirmed')).toBeInTheDocument()
    expect(screen.queryByTestId('async-loading')).toBeNull()
  })

  it('shows an error with retry', async () => {
    vi.mocked(notificationsApi.listNotifications)
      .mockRejectedValueOnce(new ApiError(500, 'server_error', 'Boom'))
      .mockResolvedValue(pageOf([unread]))
    renderApp('/notifications')

    expect(await screen.findByTestId('async-error')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /try again|retry/i }))
    expect(await screen.findByText('Reservation confirmed')).toBeInTheDocument()
    expect(notificationsApi.listNotifications).toHaveBeenCalledTimes(2)
  })

  it('shows an empty state', async () => {
    vi.mocked(notificationsApi.listNotifications).mockResolvedValue(pageOf([]))
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 0 })
    renderApp('/notifications')

    expect(await screen.findByText('You have no notifications yet.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /mark all as read/i })).toBeNull()
  })

  it('distinguishes unread from read rows and only offers mark-read on unread', async () => {
    vi.mocked(notificationsApi.listNotifications).mockResolvedValue(pageOf([unread, read]))
    renderApp('/notifications')

    const unreadRow = (await screen.findByText('Reservation confirmed')).closest('li')!
    const readRow = screen.getByText('Reservation rejected').closest('li')!
    expect(unreadRow).toHaveAttribute('data-read', 'false')
    expect(readRow).toHaveAttribute('data-read', 'true')
    expect(within(unreadRow).getByText('New')).toBeInTheDocument()
    expect(within(readRow).getByText('Read')).toBeInTheDocument()
    expect(within(unreadRow).getByRole('button', { name: 'Mark as read' })).toBeInTheDocument()
    expect(within(readRow).queryByRole('button', { name: 'Mark as read' })).toBeNull()
    expect(within(unreadRow).getByText(/now confirmed/)).toBeInTheDocument()
    expect(unreadRow.querySelector('time')).toHaveAttribute('dateTime', unread.created_at)
  })

  it('paginates through the backend pages', async () => {
    vi.mocked(notificationsApi.listNotifications).mockImplementation(async (page = 1) =>
      page === 1
        ? pageOf([unread], { count: 21, next: 'http://x/?page=2' })
        : pageOf([read], { count: 21, previous: 'http://x/?page=1' }),
    )
    renderApp('/notifications')

    expect(await screen.findByText('Reservation confirmed')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(await screen.findByText('Reservation rejected')).toBeInTheDocument()
    expect(notificationsApi.listNotifications).toHaveBeenLastCalledWith(2, expect.anything())
  })

  it('marks one notification read, reloads the list and refreshes the count from the backend', async () => {
    vi.mocked(notificationsApi.listNotifications)
      .mockResolvedValueOnce(pageOf([unread]))
      .mockResolvedValue(pageOf([{ ...unread, is_read: true, read_at: '2026-09-30T12:00:00Z' }]))
    vi.mocked(notificationsApi.markRead).mockResolvedValue({ ...unread, is_read: true })
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValueOnce({ count: 1 }).mockResolvedValue({ count: 0 })
    renderApp('/notifications')

    expect(await screen.findByTestId('notifications-badge')).toHaveTextContent('1')
    await userEvent.click(await screen.findByRole('button', { name: 'Mark as read' }))

    await waitFor(() => expect(notificationsApi.markRead).toHaveBeenCalledWith(unread.id))
    await waitFor(() => expect(screen.queryByTestId('notifications-badge')).toBeNull())
    expect(screen.queryByRole('button', { name: 'Mark as read' })).toBeNull()
    expect(notificationsApi.listNotifications).toHaveBeenCalledTimes(2)
  })

  it('disables the button while a mark-read call is in flight and sends one request', async () => {
    const pending = deferred<AppNotification>()
    vi.mocked(notificationsApi.listNotifications).mockResolvedValue(pageOf([unread]))
    vi.mocked(notificationsApi.markRead).mockReturnValue(pending.promise)
    renderApp('/notifications')

    const button = await screen.findByRole('button', { name: 'Mark as read' })
    await userEvent.click(button)
    await waitFor(() => expect(button).toBeDisabled())
    await userEvent.click(button)
    expect(notificationsApi.markRead).toHaveBeenCalledTimes(1)
    pending.resolve({ ...unread, is_read: true })
  })

  it('shows the typed error when marking fails and keeps the row unread', async () => {
    vi.mocked(notificationsApi.listNotifications).mockResolvedValue(pageOf([unread]))
    vi.mocked(notificationsApi.markRead).mockRejectedValue(new ApiError(404, 'not_found', 'Not found.'))
    renderApp('/notifications')

    await userEvent.click(await screen.findByRole('button', { name: 'Mark as read' }))
    expect(await screen.findByText('Not found.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mark as read' })).toBeEnabled()
  })

  it('marks all read, is disabled in flight, and takes the new count from the backend', async () => {
    const pending = deferred<{ updated: number }>()
    vi.mocked(notificationsApi.listNotifications)
      .mockResolvedValueOnce(pageOf([unread, note({ id: '10000000-0000-4000-8000-000000000003' })]))
      .mockResolvedValue(pageOf([{ ...unread, is_read: true }]))
    vi.mocked(notificationsApi.markAllRead).mockReturnValue(pending.promise)
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValueOnce({ count: 2 }).mockResolvedValue({ count: 0 })
    renderApp('/notifications')

    expect(await screen.findByTestId('notifications-badge')).toHaveTextContent('2')
    const all = screen.getByRole('button', { name: 'Mark all as read' })
    await userEvent.click(all)
    await waitFor(() => expect(all).toBeDisabled())
    await userEvent.click(all)
    expect(notificationsApi.markAllRead).toHaveBeenCalledTimes(1)

    pending.resolve({ updated: 2 })
    await waitFor(() => expect(screen.queryByTestId('notifications-badge')).toBeNull())
  })

  it('renders Arabic title, body-free fallback and Arabic chrome', async () => {
    await changeLanguage('ar')
    vi.mocked(notificationsApi.listNotifications).mockResolvedValue(
      pageOf([note({ title: 'تم تأكيد الحجز', body: '' }), note({ id: '1', is_read: true, title: 'مقروء' })]),
    )
    renderApp('/notifications')

    expect(await screen.findByText('تم تأكيد الحجز')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'الإشعارات' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'تحديد الكل كمقروء' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'تحديد كمقروء' })).toBeInTheDocument()
  })

  it('links a patient to their reservations', async () => {
    vi.mocked(notificationsApi.listNotifications).mockResolvedValue(pageOf([unread]))
    renderApp('/notifications')
    const link = await screen.findByRole('link', { name: 'View' })
    expect(link).toHaveAttribute('href', '/reservations')
  })

  it('links a provider to provider reservations', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PROVIDER' }))
    vi.mocked(notificationsApi.listNotifications).mockResolvedValue(pageOf([unread]))
    renderApp('/notifications')
    const link = await screen.findByRole('link', { name: 'View' })
    expect(link).toHaveAttribute('href', '/provider/reservations')
  })

  it('invents no route for unknown resources or other roles', async () => {
    vi.mocked(notificationsApi.listNotifications).mockResolvedValue(
      pageOf([note({ resource_type: 'JOB_OFFER' }), note({ id: '2', resource_type: '', resource_id: null })]),
    )
    renderApp('/notifications')
    await screen.findAllByText('Reservation confirmed')
    expect(screen.queryByRole('link', { name: 'View' })).toBeNull()
  })

  it('invents no route for a role without a reservations page', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'MEDICAL_COMPANY' }))
    vi.mocked(notificationsApi.listNotifications).mockResolvedValue(pageOf([unread]))
    renderApp('/notifications')
    await screen.findByText('Reservation confirmed')
    expect(screen.queryByRole('link', { name: 'View' })).toBeNull()
  })

  it('surfaces a notification created after login: navigation refreshes the badge and Mark all works', async () => {
    vi.mocked(notificationsApi.getUnreadCount)
      .mockResolvedValueOnce({ count: 0 })
      .mockResolvedValue({ count: 1 })
    vi.mocked(notificationsApi.listNotifications).mockResolvedValue(pageOf([unread]))
    const { router } = renderApp('/profile')
    await waitFor(() => expect(notificationsApi.getUnreadCount).toHaveBeenCalledTimes(1))
    expect(screen.queryByTestId('notifications-badge')).toBeNull()

    await act(async () => {
      await router.navigate('/notifications')
    })

    expect(await screen.findByText('Reservation confirmed')).toBeInTheDocument()
    expect(await screen.findByTestId('notifications-badge')).toHaveTextContent('1')
    expect(screen.getByRole('button', { name: 'Mark all as read' })).toBeEnabled()
  })

  it('does not disable Mark all because the unread count is stale at zero', async () => {
    // The badge says 0 (stale or delayed) but the list plainly contains an unread row.
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 0 })
    vi.mocked(notificationsApi.listNotifications).mockResolvedValue(pageOf([unread]))
    vi.mocked(notificationsApi.markAllRead).mockResolvedValue({ updated: 1 })
    renderApp('/notifications')

    const all = await screen.findByRole('button', { name: 'Mark all as read' })
    await waitFor(() => expect(notificationsApi.getUnreadCount).toHaveBeenCalledTimes(1))
    expect(all).toBeEnabled()

    await userEvent.click(all)
    await waitFor(() => expect(notificationsApi.markAllRead).toHaveBeenCalledTimes(1))
    // After success the backend count is asked for again; nothing is computed locally.
    await waitFor(() => expect(notificationsApi.getUnreadCount).toHaveBeenCalledTimes(2))
  })

  it('requires authentication', async () => {
    tokenStore.clear()
    const { router } = renderApp('/notifications')
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(notificationsApi.listNotifications).not.toHaveBeenCalled()
    expect(notificationsApi.getUnreadCount).not.toHaveBeenCalled()
  })
})
