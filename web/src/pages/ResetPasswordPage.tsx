import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'

import { auth as authApi } from '../api'
import { Alert, ApiActionButton, FormActions, LinkButton, PasswordField, useFormErrors } from '../design-system'
import { AuthShell, AuthSuccess } from './auth/AuthShell'
import { PasswordRules } from './RegisterPage'
import { ClientValidationError, PASSWORD_MIN_LENGTH } from './validation'

const FIELDS = ['new_password', 'confirm_password', 'token'] as const

export function ResetPasswordPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const uid = params.get('uid') ?? ''
  const token = params.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [done, setDone] = useState(false)
  const errors = useFormErrors(FIELDS)

  const linkInvalid = !uid || !token || errors.fieldErrors.token !== undefined

  const submit = async () => {
    const next: Partial<Record<(typeof FIELDS)[number], string>> = {}
    if (!password) next.new_password = t('validation.required')
    else if (password.length < PASSWORD_MIN_LENGTH) next.new_password = t('validation.passwordMin')
    if (confirm !== password) next.confirm_password = t('validation.passwordMismatch')
    errors.setFieldErrors(next)
    errors.setFormError(null)
    if (Object.keys(next).length > 0) throw new ClientValidationError()
    return authApi.confirmPasswordReset({ uid, token, new_password: password })
  }

  if (done) {
    return (
      <AuthShell title={t('reset.title')}>
        <AuthSuccess>
          <Alert kind="success">{t('reset.success')}</Alert>
          <div>
            <LinkButton to="/login">{t('nav.login')}</LinkButton>
          </div>
        </AuthSuccess>
      </AuthShell>
    )
  }

  if (linkInvalid) {
    return (
      <AuthShell title={t('reset.title')}>
        <AuthSuccess>
          <Alert kind="error">{errors.fieldErrors.token ?? t('reset.invalidLink')}</Alert>
          <div>
            <Link to="/forgot-password">{t('reset.requestNew')}</Link>
          </div>
        </AuthSuccess>
      </AuthShell>
    )
  }

  return (
    <AuthShell title={t('reset.title')} description={t('reset.intro')}>
      <form noValidate onSubmit={(event) => event.preventDefault()}>
        {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
        <PasswordField
          label={t('fields.newPassword')}
          name="new_password"
          autoComplete="new-password"
          dir="ltr"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={errors.fieldErrors.new_password}
          hint={<PasswordRules />}
          required
        />
        <PasswordField
          label={t('fields.confirmPassword')}
          name="confirm_password"
          autoComplete="new-password"
          dir="ltr"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={errors.fieldErrors.confirm_password}
          required
        />
        <FormActions>
          <ApiActionButton
            type="submit"
            size="lg"
            action={submit}
            onSuccess={() => setDone(true)}
            onError={(error) => {
              if (!(error instanceof ClientValidationError)) errors.applyApiError(error)
            }}
            pendingLabel={t('reset.submitting')}
          >
            {t('reset.submit')}
          </ApiActionButton>
        </FormActions>
      </form>
    </AuthShell>
  )
}
