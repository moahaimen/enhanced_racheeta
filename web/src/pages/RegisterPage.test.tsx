import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as authApi from '../api/endpoints/auth'
import { tokenStore } from '../api/tokens'
import { deferred, makeAccount, renderApp } from '../test/renderApp'

vi.mock('../api/endpoints/auth')

async function fillValid() {
  await userEvent.type(screen.getByLabelText(/الاسم الكامل|full name/i), 'New Person')
  await userEvent.type(screen.getByLabelText(/البريد الإلكتروني|email/i), 'new@example.com')
  await userEvent.type(screen.getByLabelText(/^كلمة المرور$|^password$/i), 'Str0ng-Passw0rd!')
  await userEvent.type(screen.getByLabelText(/تأكيد كلمة المرور|confirm password/i), 'Str0ng-Passw0rd!')
}

const submitButton = () => screen.getByRole('button', { name: /إنشاء الحساب|^create account$/i })

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
  })

  it('never offers the ADMIN role', () => {
    renderApp('/register')
    const select = screen.getByLabelText(/نوع الحساب|account type/i)
    const options = within(select).getAllByRole('option').map((o) => (o as HTMLOptionElement).value)
    expect(options).toEqual(['PATIENT', 'PROVIDER', 'MEDICAL_COMPANY', 'REAL_ESTATE_SELLER'])
  })

  it('shows the password rules', () => {
    renderApp('/register')
    expect(screen.getByText(/شروط كلمة المرور|password rules/i)).toBeInTheDocument()
  })

  it('rejects mismatched passwords on the client', async () => {
    renderApp('/register')
    await fillValid()
    await userEvent.clear(screen.getByLabelText(/تأكيد كلمة المرور|confirm password/i))
    await userEvent.type(screen.getByLabelText(/تأكيد كلمة المرور|confirm password/i), 'different-1')
    await userEvent.click(submitButton())
    expect(await screen.findByRole('alert')).toHaveTextContent(/غير متطابقتين|do not match/i)
    expect(authApi.register).not.toHaveBeenCalled()
  })

  it('registers with only account-level fields, shows loading, then redirects', async () => {
    const pending = deferred<{ account: ReturnType<typeof makeAccount>; tokens: { access: string; refresh: string } }>()
    vi.mocked(authApi.register).mockReturnValue(pending.promise)
    const { router } = renderApp('/register')
    await fillValid()
    await userEvent.selectOptions(screen.getByLabelText(/نوع الحساب|account type/i), 'PROVIDER')
    const submit = submitButton()
    await userEvent.click(submit)

    expect(submit).toBeDisabled()
    expect(submit).toHaveTextContent(/جارٍ الإنشاء|creating/i)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(authApi.register).toHaveBeenCalledTimes(1)
    const payload = vi.mocked(authApi.register).mock.calls[0]![0]
    expect(payload).toEqual({
      full_name: 'New Person',
      email: 'new@example.com',
      password: 'Str0ng-Passw0rd!',
      role: 'PROVIDER',
      preferred_language: 'ar',
    })
    expect(Object.keys(payload)).not.toContain('is_staff')

    pending.resolve({ account: makeAccount({ role: 'PROVIDER' }), tokens: { access: 'a', refresh: 'r' } })
    await waitFor(() => expect(router.state.location.pathname).toBe('/profile'))
  })

  it('shows the duplicate-email error from the backend on the email field', async () => {
    vi.mocked(authApi.register).mockRejectedValue(
      new ApiError(400, 'validation_error', 'Validation failed.', {
        email: ['An account with this email already exists.'],
      }),
    )
    renderApp('/register')
    await fillValid()
    await userEvent.click(submitButton())
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('already exists')
    expect(screen.getByLabelText(/البريد الإلكتروني|email/i)).toHaveAttribute('aria-invalid', 'true')
    expect(submitButton()).toBeEnabled()
  })

  it('shows backend password rule violations on the password field', async () => {
    vi.mocked(authApi.register).mockRejectedValue(
      new ApiError(400, 'validation_error', 'Validation failed.', {
        password: ['This password is too common.'],
      }),
    )
    renderApp('/register')
    await fillValid()
    await userEvent.click(submitButton())
    expect(await screen.findByRole('alert')).toHaveTextContent('too common')
  })
})
