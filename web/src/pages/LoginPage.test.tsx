import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as authApi from '../api/endpoints/auth'
import { tokenStore } from '../api/tokens'
import { deferred, makeAccount, renderApp } from '../test/renderApp'

vi.mock('../api/endpoints/auth')

function fields() {
  return {
    email: screen.getByLabelText(/البريد الإلكتروني|email/i),
    password: screen.getByLabelText(/^كلمة المرور$|^password$/i),
    submit: screen.getByRole('button', { name: /^دخول$|^log in$/i }),
  }
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
  })

  it('validates on the client before calling the backend', async () => {
    renderApp('/login')
    const { email, submit } = fields()
    await userEvent.type(email, 'not-an-email')
    await userEvent.click(submit)
    expect(await screen.findAllByRole('alert')).toHaveLength(2)
    expect(authApi.login).not.toHaveBeenCalled()
  })

  it('disables the button and shows the spinner while logging in, then redirects', async () => {
    const pending = deferred<{ access: string; refresh: string }>()
    vi.mocked(authApi.login).mockReturnValue(pending.promise)
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount())

    const { router } = renderApp('/login')
    const { email, password, submit } = fields()
    await userEvent.type(email, 'person@example.com')
    await userEvent.type(password, 'Str0ng-Passw0rd!')
    await userEvent.click(submit)

    expect(submit).toBeDisabled()
    expect(submit).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('status')).toBeInTheDocument()
    await userEvent.click(submit) // duplicate click ignored
    expect(authApi.login).toHaveBeenCalledTimes(1)
    expect(authApi.login).toHaveBeenCalledWith({
      email: 'person@example.com',
      password: 'Str0ng-Passw0rd!',
    })

    pending.resolve({ access: 'a', refresh: 'r' })
    await waitFor(() => expect(router.state.location.pathname).toBe('/profile'))
  })

  it('submits with the Enter key', async () => {
    vi.mocked(authApi.login).mockResolvedValue({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount())
    const { router } = renderApp('/login')
    const { email, password } = fields()
    await userEvent.type(email, 'person@example.com')
    await userEvent.type(password, 'Str0ng-Passw0rd!{Enter}')
    await waitFor(() => expect(router.state.location.pathname).toBe('/profile'))
    expect(authApi.login).toHaveBeenCalledTimes(1)
  })

  it('shows a generic message on wrong credentials and restores the button', async () => {
    vi.mocked(authApi.login).mockRejectedValue(
      new ApiError(401, 'no_active_account', 'No active account found'),
    )
    renderApp('/login')
    const { email, password, submit } = fields()
    await userEvent.type(email, 'person@example.com')
    await userEvent.type(password, 'wrong-password')
    await userEvent.click(submit)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/تعذّر تسجيل الدخول|could not log in/i)
    expect(submit).toBeEnabled()
    expect(tokenStore.isAuthenticated()).toBe(false)
  })

  it('maps backend field errors onto the fields', async () => {
    vi.mocked(authApi.login).mockRejectedValue(
      new ApiError(400, 'validation_error', 'Validation failed.', {
        email: ['Enter a valid email address.'],
      }),
    )
    renderApp('/login')
    const { email, password, submit } = fields()
    await userEvent.type(email, 'person@example.com')
    await userEvent.type(password, 'whatever-123')
    await userEvent.click(submit)
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a valid email address.')
    expect(email).toHaveAttribute('aria-invalid', 'true')
  })

  it('toggles password visibility', async () => {
    renderApp('/login')
    const { password } = fields()
    expect(password).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: /إظهار كلمة المرور|show password/i }))
    expect(password).toHaveAttribute('type', 'text')
  })

  it('returns to the page the visitor came from', async () => {
    vi.mocked(authApi.login).mockResolvedValue({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount())
    const { router } = renderApp('/profile') // guard redirects to /login with state.from
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    const { email, password, submit } = fields()
    await userEvent.type(email, 'person@example.com')
    await userEvent.type(password, 'Str0ng-Passw0rd!')
    await userEvent.click(submit)
    await waitFor(() => expect(router.state.location.pathname).toBe('/profile'))
  })
})
