import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as authApi from '../api/endpoints/auth'
import { tokenStore } from '../api/tokens'
import { deferred, renderApp } from '../test/renderApp'

vi.mock('../api/endpoints/auth')

describe('ForgotPasswordPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
  })

  it('shows the same enumeration-safe message after submitting', async () => {
    const pending = deferred<{ detail: string }>()
    vi.mocked(authApi.requestPasswordReset).mockReturnValue(pending.promise)
    renderApp('/forgot-password')
    await userEvent.type(screen.getByLabelText(/البريد الإلكتروني|email/i), 'anyone@example.com')
    const submit = screen.getByRole('button', { name: /إرسال الرابط|send reset link/i })
    await userEvent.click(submit)
    expect(submit).toBeDisabled()
    expect(screen.getByRole('status')).toBeInTheDocument()
    pending.resolve({ detail: 'ok' })
    expect(await screen.findByText(/إذا كان هناك حساب|if an account exists/i)).toBeInTheDocument()
    expect(authApi.requestPasswordReset).toHaveBeenCalledWith({ email: 'anyone@example.com' })
  })

  it('validates the email on the client', async () => {
    renderApp('/forgot-password')
    await userEvent.click(screen.getByRole('button', { name: /إرسال الرابط|send reset link/i }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(authApi.requestPasswordReset).not.toHaveBeenCalled()
  })
})

describe('ResetPasswordPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
  })

  it('rejects a link without uid/token', () => {
    renderApp('/reset-password')
    expect(screen.getByRole('alert')).toHaveTextContent(/غير صالح|invalid/i)
    expect(screen.getByRole('link', { name: /اطلب رابطاً جديداً|request a new link/i })).toBeInTheDocument()
  })

  it('confirms the new password and offers the login link', async () => {
    vi.mocked(authApi.confirmPasswordReset).mockResolvedValue({ detail: 'ok' })
    renderApp('/reset-password?uid=abc&token=xyz-123')
    await userEvent.type(screen.getByLabelText(/كلمة المرور الجديدة|new password/i), 'An0ther-Str0ng-One!')
    await userEvent.type(screen.getByLabelText(/تأكيد كلمة المرور|confirm password/i), 'An0ther-Str0ng-One!')
    await userEvent.click(screen.getByRole('button', { name: /حفظ كلمة المرور|save password/i }))
    expect(await screen.findByText(/تم تغيير كلمة المرور|password was changed/i)).toBeInTheDocument()
    expect(authApi.confirmPasswordReset).toHaveBeenCalledWith({
      uid: 'abc',
      token: 'xyz-123',
      new_password: 'An0ther-Str0ng-One!',
    })
    const main = within(screen.getByRole('main'))
    expect(main.getByRole('link', { name: /تسجيل الدخول|log in/i })).toHaveAttribute('href', '/login')
  })

  it('shows the invalid-link state when the backend rejects the token', async () => {
    vi.mocked(authApi.confirmPasswordReset).mockRejectedValue(
      new ApiError(400, 'validation_error', 'Validation failed.', {
        token: ['This link is invalid or has expired. Request a new one.'],
      }),
    )
    renderApp('/reset-password?uid=abc&token=expired')
    await userEvent.type(screen.getByLabelText(/كلمة المرور الجديدة|new password/i), 'An0ther-Str0ng-One!')
    await userEvent.type(screen.getByLabelText(/تأكيد كلمة المرور|confirm password/i), 'An0ther-Str0ng-One!')
    await userEvent.click(screen.getByRole('button', { name: /حفظ كلمة المرور|save password/i }))
    await waitFor(() =>
      expect(screen.getByRole('link', { name: /اطلب رابطاً جديداً|request a new link/i })).toBeInTheDocument(),
    )
  })

  it('shows backend password-rule errors and keeps the form', async () => {
    vi.mocked(authApi.confirmPasswordReset).mockRejectedValue(
      new ApiError(400, 'validation_error', 'Validation failed.', {
        new_password: ['This password is too common.'],
      }),
    )
    renderApp('/reset-password?uid=abc&token=t')
    await userEvent.type(screen.getByLabelText(/كلمة المرور الجديدة|new password/i), 'password1')
    await userEvent.type(screen.getByLabelText(/تأكيد كلمة المرور|confirm password/i), 'password1')
    await userEvent.click(screen.getByRole('button', { name: /حفظ كلمة المرور|save password/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('too common')
    expect(screen.getByRole('button', { name: /حفظ كلمة المرور|save password/i })).toBeEnabled()
  })
})

describe('VerifyEmailPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
  })

  it('confirms on load and shows success', async () => {
    vi.mocked(authApi.confirmEmailVerification).mockResolvedValue({ detail: 'ok' })
    renderApp('/verify-email?uid=u&token=t')
    expect(await screen.findByText(/تم تأكيد بريدك|is verified/i)).toBeInTheDocument()
    expect(authApi.confirmEmailVerification).toHaveBeenCalledWith({ uid: 'u', token: 't' })
  })

  it('shows the invalid-link message on failure', async () => {
    vi.mocked(authApi.confirmEmailVerification).mockRejectedValue(
      new ApiError(400, 'validation_error', 'Validation failed.', { token: ['bad'] }),
    )
    renderApp('/verify-email?uid=u&token=t')
    expect(await screen.findByRole('alert')).toHaveTextContent(/غير صالح|invalid/i)
  })
})
