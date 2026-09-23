import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate } from 'react-router'

import { ApiError } from '../api'
import { DEFAULT_AUTHENTICATED_PATH } from '../app/guards'
import { useAuth } from '../auth/useAuth'
import { ApiActionButton } from '../components'
import { FormAlert, PasswordField, TextField, useFormErrors } from '../components/forms'
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
    <section className="card card--form">
      <h2>{t('login.title')}</h2>
      <form noValidate onSubmit={(event: FormEvent) => event.preventDefault()}>
        {errors.formError ? <FormAlert kind="error">{errors.formError}</FormAlert> : null}
        <TextField
          label={t('fields.email')}
          type="email"
          name="email"
          autoComplete="email"
          inputMode="email"
          dir="ltr"
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
        <div className="form__actions">
          <ApiActionButton
            type="submit"
            action={submit}
            onSuccess={onSuccess}
            onError={onError}
            pendingLabel={t('login.submitting')}
          >
            {t('login.submit')}
          </ApiActionButton>
          <Link to="/forgot-password" className="link">
            {t('login.forgot')}
          </Link>
        </div>
      </form>
      <p className="form__footer">
        {t('login.noAccount')} <Link to="/register">{t('login.register')}</Link>
      </p>
    </section>
  )
}
