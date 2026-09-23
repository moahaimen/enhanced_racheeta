import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { auth as authApi } from '../api'
import { ApiActionButton } from '../components'
import { FormAlert, TextField, useFormErrors } from '../components/forms'
import { ClientValidationError, isEmail } from './validation'

export function ForgotPasswordPage() {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const errors = useFormErrors(['email'] as const)

  const submit = async () => {
    errors.clear()
    if (!email.trim()) {
      errors.setFieldErrors({ email: t('validation.required') })
      throw new ClientValidationError()
    }
    if (!isEmail(email)) {
      errors.setFieldErrors({ email: t('validation.email') })
      throw new ClientValidationError()
    }
    return authApi.requestPasswordReset({ email: email.trim() })
  }

  return (
    <section className="card card--form">
      <h2>{t('forgot.title')}</h2>
      {sent ? (
        <>
          <FormAlert kind="success">{t('forgot.sent')}</FormAlert>
          <p className="form__footer">
            <Link to="/login">{t('forgot.backToLogin')}</Link>
          </p>
        </>
      ) : (
        <form noValidate onSubmit={(event) => event.preventDefault()}>
          <p>{t('forgot.intro')}</p>
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
          <div className="form__actions">
            <ApiActionButton
              type="submit"
              action={submit}
              onSuccess={() => setSent(true)}
              onError={(error) => {
                if (!(error instanceof ClientValidationError)) errors.applyApiError(error)
              }}
              pendingLabel={t('forgot.submitting')}
            >
              {t('forgot.submit')}
            </ApiActionButton>
            <Link to="/login" className="link">
              {t('forgot.backToLogin')}
            </Link>
          </div>
        </form>
      )}
    </section>
  )
}
