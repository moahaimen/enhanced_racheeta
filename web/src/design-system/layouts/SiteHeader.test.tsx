import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../../api/endpoints/auth'
import * as notificationsApi from '../../api/endpoints/notifications'
import * as providersApi from '../../api/endpoints/providers'
import * as referenceApi from '../../api/endpoints/reference'
import { tokenStore } from '../../api/tokens'
import { changeLanguage } from '../../i18n'
import { mockHomeData } from '../../test/homeMocks'
import { makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/providers')
vi.mock('../../api/endpoints/reference')
vi.mock('../../api/endpoints/jobs')
vi.mock('../../api/endpoints/realEstate')
vi.mock('../../api/endpoints/marketplace')

type Role = 'PATIENT' | 'PROVIDER' | 'MEDICAL_COMPANY' | 'REAL_ESTATE_SELLER'

async function signIn(role: Role, isStaff = false) {
  tokenStore.set({ access: 'a', refresh: 'r' })
  vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role, is_staff: isStaff }))
  renderApp('/')
  return screen.findByRole('button', { name: /workspace/i })
}

const hrefs = (root: HTMLElement) =>
  within(root)
    .getAllByRole('link')
    .map((link) => link.getAttribute('href'))

describe('SiteHeader on desktop', () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    mockHomeData()
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 0 })
    vi.mocked(providersApi.listProviders).mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
    vi.mocked(referenceApi.listSpecialties).mockResolvedValue([])
    await changeLanguage('en')
    tokenStore.clear()
  })

  it('keeps the public navigation to five links and lists no account destinations in the bar', async () => {
    await signIn('PROVIDER')
    const nav = screen.getAllByRole('navigation', { name: /main/i })[0]!
    expect(hrefs(nav)).toEqual(['/', '/providers', '/providers?kind=FACILITY', '/jobs', '/real-estate'])
  })

  it('groups every account destination of a provider in the account menu, once', async () => {
    const button = await signIn('PROVIDER')
    const panel = document.getElementById(button.getAttribute('aria-controls')!)!
    expect(hrefs(panel)).toEqual([
      '/dashboard',
      '/provider/profile',
      '/provider/reservations',
      '/provider/offers',
      '/marketplace',
      '/employer',
      '/profile',
    ])
  })

  it.each([
    ['PATIENT', '/reservations', ['/marketplace', '/company', '/real-estate/owner']],
    ['MEDICAL_COMPANY', '/company', ['/marketplace', '/reservations', '/provider/profile']],
    ['REAL_ESTATE_SELLER', '/real-estate/owner', ['/marketplace', '/company', '/reservations']],
  ] as const)('shows only the %s destinations in the menu', async (role, present, absent) => {
    const button = await signIn(role)
    const links = hrefs(document.getElementById(button.getAttribute('aria-controls')!)!)
    expect(links).toContain(present)
    for (const href of absent) expect(links).not.toContain(href)
    expect(links).toContain('/dashboard')
    expect(links).toContain('/profile')
  })

  it('offers the admin console to staff only', async () => {
    const button = await signIn('PATIENT', true)
    expect(hrefs(document.getElementById(button.getAttribute('aria-controls')!)!)).toContain('/admin-console')
  })

  it('toggles with the button, closes on Escape and returns focus to it', async () => {
    const user = userEvent.setup()
    const button = await signIn('PATIENT')
    const panel = document.getElementById(button.getAttribute('aria-controls')!)!
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(panel).toHaveAttribute('data-open', 'false')

    await user.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(panel).toHaveAttribute('data-open', 'true')

    await user.keyboard('{Escape}')
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(button).toHaveFocus()
  })

  it('closes on an outside click and after choosing a destination', async () => {
    const user = userEvent.setup()
    const button = await signIn('PATIENT')
    await user.click(button)
    await user.click(document.body)
    expect(button).toHaveAttribute('aria-expanded', 'false')

    await user.click(button)
    await user.click(within(document.getElementById(button.getAttribute('aria-controls')!)!).getByRole('link', { name: /^my account$/i }))
    await waitFor(() => expect(button).toHaveAttribute('aria-expanded', 'false'))
  })

  it('reaches the menu by keyboard: the button is a real, focusable button', async () => {
    const user = userEvent.setup()
    const button = await signIn('PATIENT')
    button.focus()
    await user.keyboard('{Enter}')
    expect(button).toHaveAttribute('aria-expanded', 'true')
  })

  it('keeps the inbox shortcuts and their badges outside the menu, with accessible names', async () => {
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 7 })
    const button = await signIn('PATIENT')
    const panel = document.getElementById(button.getAttribute('aria-controls')!)!
    const bell = await screen.findByRole('link', { name: /notifications/i })
    expect(bell).toHaveAttribute('href', '/notifications')
    expect(panel).not.toContainElement(bell)
    expect(await screen.findByTestId('notifications-badge')).toHaveTextContent('7')
    const messages = screen.getByRole('link', { name: /messages/i })
    expect(messages).toHaveAttribute('href', '/messages')
    expect(panel).not.toContainElement(messages)
  })

  it('shows the person and role at the top of the menu and a logout action', async () => {
    const button = await signIn('PROVIDER')
    const panel = document.getElementById(button.getAttribute('aria-controls')!)!
    expect(within(panel).getByText('Test Person')).toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: /log ?out|sign out/i })).toBeInTheDocument()
  })

  it('renders no account menu for an anonymous visitor, only login and register', async () => {
    renderApp('/')
    await screen.findAllByRole('link', { name: /create account/i })
    expect(screen.queryByRole('button', { name: /workspace/i })).toBeNull()
    expect(screen.getAllByRole('link', { name: /log ?in|sign in/i }).length).toBeGreaterThan(0)
  })
})

describe('SiteHeader mobile panel', () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    mockHomeData()
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 0 })
    await changeLanguage('en')
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'MEDICAL_COMPANY' }))
  })

  it('lists every route in one panel so nothing is lost on a phone', async () => {
    const user = userEvent.setup()
    renderApp('/')
    await user.click(await screen.findByRole('button', { name: /open menu/i }))
    const panel = document.getElementById('mobile-nav')!
    const links = hrefs(panel)
    for (const href of ['/', '/providers', '/jobs', '/real-estate', '/dashboard', '/company', '/company/advertising', '/employer', '/profile', '/messages', '/notifications']) {
      expect(links).toContain(href)
    }
    expect(within(panel).getByRole('button', { name: /log ?out|sign out/i })).toBeInTheDocument()
  })
})
