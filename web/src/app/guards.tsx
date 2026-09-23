/**
 * Route guards. All authentication checks live here, never in pages.
 */
import { useTranslation } from 'react-i18next'
import { Navigate, Outlet, useLocation } from 'react-router'

import type { AccountRole } from '../api'
import { useAuth } from '../auth/useAuth'
import { ErrorState, LoadingState } from '../design-system'

export const DEFAULT_AUTHENTICATED_PATH = '/profile'

export function SessionRestoring() {
  const { t } = useTranslation()
  return <LoadingState label={t('common.restoringSession')} testId="session-restoring" />
}

/** Children render only for authenticated users; others go to /login. */
export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'restoring') return <SessionRestoring />
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return <Outlet />
}

/** Login/register pages: an authenticated user is sent on to the app. */
export function PublicOnly() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'restoring') return <SessionRestoring />
  if (status === 'authenticated') {
    const from = (location.state as { from?: string } | null)?.from
    return <Navigate to={from && from !== '/login' ? from : DEFAULT_AUTHENTICATED_PATH} replace />
  }
  return <Outlet />
}

/** Inside RequireAuth: only accounts with one of `roles` may proceed. */
export function RequireRole({ roles }: { roles: AccountRole[] }) {
  const { account } = useAuth()
  const { t } = useTranslation()
  if (!account || !roles.includes(account.role)) {
    return (
      <div role="alert" data-testid="role-denied">
        <ErrorState title={t('providerProfile.notProvider')} error={null} />
      </div>
    )
  }
  return <Outlet />
}
