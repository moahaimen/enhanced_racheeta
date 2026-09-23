import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'

import { routes } from '../app/routes'
import { AuthProvider } from '../auth/AuthContext'
import { initI18n } from '../i18n'
import type { Account } from '../api'

initI18n()

/** Mounts the real route table at `path` inside the real AuthProvider. */
export function renderApp(path = '/') {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const utils = render(
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>,
  )
  return { ...utils, router }
}

export function makeAccount(overrides: Partial<Account> = {}): Account {
  return {
    id: '11111111-1111-4111-8111-111111111111',
    email: 'person@example.com',
    full_name: 'Test Person',
    phone_number: '',
    role: 'PATIENT',
    preferred_language: 'ar',
    email_verified: false,
    email_verified_at: null,
    has_password: true,
    is_staff: false,
    permissions: ['accounts.edit_self', 'accounts.view_self'],
    created_at: '2026-09-23T10:00:00Z',
    last_login: null,
    ...overrides,
  }
}

export function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}
