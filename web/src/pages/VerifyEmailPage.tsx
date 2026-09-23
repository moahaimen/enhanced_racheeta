import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'

import { ApiError, auth as authApi } from '../api'
import { useAuth } from '../auth/useAuth'
import { FormAlert } from '../components/forms'
import { AsyncPage } from '../components'

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
    <section className="card card--form">
      <h2>{t('verifyEmail.title')}</h2>
      <AsyncPage load={confirm} loadingLabel={t('verifyEmail.verifying')}>
        {() => (
          <>
            <FormAlert kind="success">{t('verifyEmail.success')}</FormAlert>
            <p className="form__footer">
              <Link to={status === 'authenticated' ? '/profile' : '/login'} className="btn">
                {status === 'authenticated' ? t('nav.profile') : t('nav.login')}
              </Link>
            </p>
          </>
        )}
      </AsyncPage>
    </section>
  )
}
