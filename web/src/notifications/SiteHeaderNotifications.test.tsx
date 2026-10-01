import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../api/endpoints/auth'
import * as notificationsApi from '../api/endpoints/notifications'
import { tokenStore } from '../api/tokens'
import { changeLanguage } from '../i18n'
import { makeAccount, renderApp } from '../test/renderApp'

vi.mock('../api/endpoints/auth')

describe('Header notifications entry', () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    await changeLanguage('en')
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PATIENT' }))
  })

  it('shows the bell link with the backend unread count', async () => {
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 3 })
    renderApp('/')

    const link = await screen.findByRole('link', { name: /notifications/i })
    expect(link).toHaveAttribute('href', '/notifications')
    expect(await screen.findByTestId('notifications-badge')).toHaveTextContent('3')
    expect(screen.getByLabelText('3 unread notifications')).toBeInTheDocument()
  })

  it('hides the badge at zero and when the count cannot be loaded', async () => {
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 0 })
    const first = renderApp('/')
    await screen.findByRole('link', { name: /notifications/i })
    await waitFor(() => expect(notificationsApi.getUnreadCount).toHaveBeenCalled())
    expect(screen.queryByTestId('notifications-badge')).toBeNull()
    first.unmount()

    vi.mocked(notificationsApi.getUnreadCount).mockRejectedValue(new Error('offline'))
    renderApp('/')
    await screen.findByRole('link', { name: /notifications/i })
    expect(screen.queryByTestId('notifications-badge')).toBeNull()
  })

  it('caps the badge at 99+', async () => {
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 150 })
    renderApp('/')
    expect(await screen.findByTestId('notifications-badge')).toHaveTextContent('99+')
  })

  it('shows exactly 99 without the plus', async () => {
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 99 })
    renderApp('/')
    expect(await screen.findByTestId('notifications-badge')).toHaveTextContent(/^99$/)
  })

  it('shows nothing for an anonymous visitor and never calls the backend', async () => {
    tokenStore.clear()
    renderApp('/')
    await screen.findAllByRole('link', { name: /create account/i })
    expect(screen.queryByRole('link', { name: /notifications/i })).toBeNull()
    expect(notificationsApi.getUnreadCount).not.toHaveBeenCalled()
  })

  it('fetches only the count: one request, no list, no polling', async () => {
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 2 })
    renderApp('/')
    await screen.findByTestId('notifications-badge')
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(notificationsApi.getUnreadCount).toHaveBeenCalledTimes(1)
    expect(notificationsApi.listNotifications).not.toHaveBeenCalled()
  })

  it('clears the badge and the link on logout', async () => {
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 4 })
    vi.mocked(authApi.logout).mockImplementation(async () => {
      tokenStore.clear()
    })
    renderApp('/')
    expect(await screen.findByTestId('notifications-badge')).toHaveTextContent('4')

    await userEvent.click(screen.getByRole('button', { name: /log out/i }))
    await screen.findAllByRole('link', { name: /create account/i })
    expect(screen.queryByTestId('notifications-badge')).toBeNull()
    expect(screen.queryByRole('link', { name: /notifications/i })).toBeNull()
  })

  it('works in the mobile menu too', async () => {
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 5 })
    renderApp('/')
    await screen.findByTestId('notifications-badge')
    await userEvent.click(screen.getByRole('button', { name: /open menu/i }))
    expect(screen.getAllByRole('link', { name: /notifications/i })).toHaveLength(2)
    expect(screen.getAllByTestId('notifications-badge')).toHaveLength(2)
  })

  it('renders the Arabic label', async () => {
    await changeLanguage('ar')
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 1 })
    renderApp('/')
    expect(await screen.findByRole('link', { name: /الإشعارات/ })).toBeInTheDocument()
    expect(await screen.findByLabelText('إشعار واحد غير مقروء')).toBeInTheDocument()
  })
})
