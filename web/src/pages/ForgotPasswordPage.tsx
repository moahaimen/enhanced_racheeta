import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { auth as authApi } from '../api'
import { Alert, ApiActionButton, FormActions, Icon, LinkButton, TextField, useFormErrors } from '../design-system'
import { AuthShell, AuthSuccess } from './auth/AuthShell'
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
    <AuthShell title={t('forgot.title')} description={sent ? undefined : t('forgot.intro')}>
      {sent ? (
        <AuthSuccess>
          <Alert kind="success">{t('forgot.sent')}</Alert>
          <div>
            <LinkButton to="/login" variant="secondary">
              {t('forgot.backToLogin')}
            </LinkButton>
          </div>
        </AuthSuccess>
      ) : (
        <form noValidate onSubmit={(event) => event.preventDefault()}>
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
          <FormActions>
            <ApiActionButton
              type="submit"
              size="lg"
              action={submit}
              onSuccess={() => setSent(true)}
              onError={(error) => {
                if (!(error instanceof ClientValidationError)) errors.applyApiError(error)
              }}
              pendingLabel={t('forgot.submitting')}
            >
              {t('forgot.submit')}
            </ApiActionButton>
            <Link to="/login">{t('forgot.backToLogin')}</Link>
          </FormActions>
        </form>
      )}
    </AuthShell>
  )
}
