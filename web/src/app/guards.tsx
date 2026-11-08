/**
 * Route guards. All authentication checks live here, never in pages.
 */
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Outlet, useLocation } from 'react-router'

import { providers as providersApi } from '../api'
import type { AccountRole } from '../api'
import { useAuth } from '../auth/useAuth'
import { ErrorState, LoadingState } from '../design-system'

/** Where a signed-in account lands: its role-aware dashboard (never a bare profile form). */
export const DEFAULT_AUTHENTICATED_PATH = '/dashboard'

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
export function RequireRole({ roles, deniedTitleKey = 'providerProfile.notProvider' }: { roles: AccountRole[]; deniedTitleKey?: string }) {
  const { account } = useAuth()
  const { t } = useTranslation()
  if (!account || !roles.includes(account.role)) {
    return (
      <div role="alert" data-testid="role-denied">
        <ErrorState title={t(deniedTitleKey)} error={null} />
      </div>
    )
  }
  return <Outlet />
}

/** Inside RequireAuth: Racheeta staff only (the account's is_staff flag, not a role). */
export function RequireStaff() {
  const { account } = useAuth()
  const { t } = useTranslation()
  if (!account?.is_staff) {
    return (
      <div role="alert" data-testid="staff-denied">
        <ErrorState title={t('errors.staffOnly')} error={null} />
      </div>
    )
  }
  return <Outlet />
}

/**
 * Store workspace pages (/company…): business accounts, and pharmacies — a PROVIDER whose own
 * provider profile is a PHARMACY keeps its provider role and runs a linked store. Any other
 * provider is refused here exactly like RequireRole does. The server re-checks everything.
 */
export function RequireStoreOwner({ deniedTitleKey = 'company.notCompany' }: { deniedTitleKey?: string }) {
  const { account } = useAuth()
  const { t } = useTranslation()
  const [pharmacy, setPharmacy] = useState<boolean | null>(null)
  const isProvider = account?.role === 'PROVIDER'
  useEffect(() => {
    if (!isProvider) return
    let alive = true
    Promise.resolve()
      .then(() => providersApi.getMyProvider())
      .then((profile) => alive && setPharmacy(profile?.provider_type === 'PHARMACY'))
      .catch(() => alive && setPharmacy(false))
    return () => {
      alive = false
    }
  }, [isProvider])
  if (account?.role === 'MEDICAL_COMPANY' || (isProvider && pharmacy === true)) return <Outlet />
  if (isProvider && pharmacy === null) return <LoadingState testId="store-owner-check" />
  return (
    <div role="alert" data-testid="role-denied">
      <ErrorState title={t(deniedTitleKey)} error={null} />
    </div>
  )
}
