import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../api/endpoints/auth'
import { tokenStore } from '../api/tokens'
import { makeAccount, renderApp } from '../test/renderApp'

vi.mock('../api/endpoints/auth')

describe('ProfilePage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(
      makeAccount({ full_name: 'Loaded From Me', role: 'PROVIDER', permissions: ['providers.manage_own_profile'] }),
    )
  })

  it('loads identity from GET /me and shows role and capabilities as hints', async () => {
    renderApp('/profile')
    expect(await screen.findByDisplayValue('Loaded From Me')).toBeInTheDocument()
    expect(screen.getByText('person@example.com')).toBeInTheDocument()
    expect(screen.getByText(/مقدّم خدمة صحية|healthcare provider/i)).toBeInTheDocument()
    expect(screen.getByText('providers.manage_own_profile')).toBeInTheDocument()
    expect(screen.getByText(/غير مؤكَّد|not verified/i)).toBeInTheDocument()
  })

  it('saves editable fields through PATCH /me with loading state', async () => {
    vi.mocked(authApi.updateMe).mockResolvedValue(makeAccount({ full_name: 'Renamed' }))
    renderApp('/profile')
    const name = await screen.findByLabelText(/الاسم الكامل|full name/i)
    await userEvent.clear(name)
    await userEvent.type(name, 'Renamed')
    const save = screen.getByRole('button', { name: /^حفظ$|^save$/i })
    await userEvent.click(save)
    await waitFor(() => expect(authApi.updateMe).toHaveBeenCalledTimes(1))
    expect(authApi.updateMe).toHaveBeenCalledWith({
      full_name: 'Renamed',
      phone_number: '',
      preferred_language: 'ar',
    })
    expect(await screen.findByRole('status')).toHaveTextContent(/تم حفظ|saved/i)
    expect(save).toBeEnabled()
  })

  it('offers to send the verification email and reports success', async () => {
    vi.mocked(authApi.requestEmailVerification).mockResolvedValue({ detail: 'sent' })
    renderApp('/profile')
    const button = await screen.findByRole('button', { name: /إرسال رسالة التأكيد|send verification/i })
    await userEvent.click(button)
    expect(await screen.findByText(/أُرسلت رسالة التأكيد|verification email sent/i)).toBeInTheDocument()
    expect(authApi.requestEmailVerification).toHaveBeenCalledTimes(1)
  })

  it('logs out from the header, calls the backend, and lands on /login', async () => {
    vi.mocked(authApi.logout).mockResolvedValue(undefined)
    const { router } = renderApp('/profile')
    const logout = await screen.findByRole('button', { name: /تسجيل الخروج|log out/i })
    await userEvent.click(logout)
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(authApi.logout).toHaveBeenCalledTimes(1)
  })
})
