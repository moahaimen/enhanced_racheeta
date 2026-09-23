import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate } from 'react-router'

import { ApiError } from '../api'
import { DEFAULT_AUTHENTICATED_PATH } from '../app/guards'
import { useAuth } from '../auth/useAuth'
import { Alert, ApiActionButton, FormActions, Icon, PasswordField, TextField, useFormErrors } from '../design-system'
import { AuthShell } from './auth/AuthShell'
import { ClientValidationError, isEmail } from './validation'

const FIELDS = ['email', 'password'] as const

export function LoginPage() {
  const { t } = useTranslation()
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const errors = useFormErrors(FIELDS)

  const validate = (): boolean => {
    const next: Partial<Record<(typeof FIELDS)[number], string>> = {}
    if (!email.trim()) next.email = t('validation.required')
    else if (!isEmail(email)) next.email = t('validation.email')
    if (!password) next.password = t('validation.required')
    errors.setFieldErrors(next)
    errors.setFormError(null)
    return Object.keys(next).length === 0
  }

  const submit = async () => {
    if (!validate()) throw new ClientValidationError()
    return login({ email: email.trim(), password })
  }

  const onSuccess = () => {
    const from = (location.state as { from?: string } | null)?.from
    navigate(from && from !== '/login' ? from : DEFAULT_AUTHENTICATED_PATH, { replace: true })
  }

  const onError = (error: unknown) => {
    if (error instanceof ClientValidationError) return
    if (error instanceof ApiError && error.status === 401) errors.setFormError(t('login.failed'))
    else errors.applyApiError(error)
  }

  return (
    <AuthShell
      title={t('login.title')}
      description={t('login.intro')}
      footer={
        <>
          {t('login.noAccount')} <Link to="/register">{t('login.register')}</Link>
        </>
      }
    >
      <form noValidate onSubmit={(event: FormEvent) => event.preventDefault()}>
        {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
        <TextField
          label={t('fields.email')}
          type="email"
          name="email"
          autoComplete="email"
          inputMode="email"
          dir="ltr"
          leading={<Icon name="mail" size={18} />}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errors.fieldErrors.email}
          required
        />
        <PasswordField
          label={t('fields.password')}
          name="password"
          autoComplete="current-password"
          dir="ltr"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={errors.fieldErrors.password}
          required
        />
        <FormActions>
          <ApiActionButton type="submit" action={submit} onSuccess={onSuccess} onError={onError} pendingLabel={t('login.submitting')} size="lg">
            {t('login.submit')}
          </ApiActionButton>
          <Link to="/forgot-password">{t('login.forgot')}</Link>
        </FormActions>
      </form>
    </AuthShell>
  )
}
