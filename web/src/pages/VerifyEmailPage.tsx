import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { ApiError, auth as authApi } from '../api'
import { useAuth } from '../auth/useAuth'
import { Alert, AsyncPage, LinkButton } from '../design-system'
import { AuthShell, AuthSuccess } from './auth/AuthShell'

/** Landing page for the link in the verification email. Confirms on load. */
export function VerifyEmailPage() {
  const { t } = useTranslation()
  const { status, refreshAccount } = useAuth()
  const [params] = useSearchParams()
  const uid = params.get('uid') ?? ''
  const token = params.get('token') ?? ''

  const confirm = async () => {
    if (!uid || !token) throw new ApiError(400, 'invalid_token', t('verifyEmail.invalidLink'))
    try {
      const result = await authApi.confirmEmailVerification({ uid, token })
      if (status === 'authenticated') await refreshAccount().catch(() => undefined)
      return result
    } catch (error) {
      if (error instanceof ApiError && error.status === 400) {
        throw new ApiError(400, 'invalid_token', t('verifyEmail.invalidLink'))
      }
      throw error
    }
  }

  return (
    <AuthShell title={t('verifyEmail.title')}>
      <AsyncPage load={confirm} loadingLabel={t('verifyEmail.verifying')}>
        {() => (
          <AuthSuccess>
            <Alert kind="success">{t('verifyEmail.success')}</Alert>
            <div>
              <LinkButton to={status === 'authenticated' ? '/profile' : '/login'}>
                {status === 'authenticated' ? t('nav.profile') : t('nav.login')}
              </LinkButton>
            </div>
          </AuthSuccess>
        )}
      </AsyncPage>
    </AuthShell>
  )
}
