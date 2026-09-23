import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router'

import type { AccountRole, PreferredLanguage } from '../api'
import { DEFAULT_AUTHENTICATED_PATH } from '../app/guards'
import { SELF_REGISTRATION_ROLES } from '../auth/roles'
import { useAuth } from '../auth/useAuth'
import { Alert, ApiActionButton, FormActions, FormSection, Icon, PasswordField, Select, TextField, useFormErrors } from '../design-system'
import { AuthShell } from './auth/AuthShell'
import { ClientValidationError, isEmail, isPhone, PASSWORD_MIN_LENGTH } from './validation'

const FIELDS = ['full_name', 'email', 'phone_number', 'password', 'confirm_password', 'role'] as const

export function RegisterPage() {
  const { t, i18n } = useTranslation()
  const { register } = useAuth()
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [role, setRole] = useState<Exclude<AccountRole, 'ADMIN'>>('PATIENT')
  const errors = useFormErrors(FIELDS)

  const validate = (): boolean => {
    const next: Partial<Record<(typeof FIELDS)[number], string>> = {}
    if (!fullName.trim()) next.full_name = t('validation.required')
    if (!email.trim()) next.email = t('validation.required')
    else if (!isEmail(email)) next.email = t('validation.email')
    if (phone.trim() && !isPhone(phone)) next.phone_number = t('validation.phone')
    if (!password) next.password = t('validation.required')
    else if (password.length < PASSWORD_MIN_LENGTH) next.password = t('validation.passwordMin')
    if (confirm !== password) next.confirm_password = t('validation.passwordMismatch')
    errors.setFieldErrors(next)
    errors.setFormError(null)
    return Object.keys(next).length === 0
  }

  const submit = async () => {
    if (!validate()) throw new ClientValidationError()
    return register({
      full_name: fullName.trim(),
      email: email.trim(),
      password,
      role,
      preferred_language: i18n.language as PreferredLanguage,
      ...(phone.trim() ? { phone_number: phone.replace(/[\s-]/g, '') } : {}),
    })
  }

  const onError = (error: unknown) => {
    if (error instanceof ClientValidationError) return
    errors.applyApiError(error)
  }

  return (
    <AuthShell
      title={t('register.title')}
      description={t('register.intro')}
      footer={
        <>
          {t('register.haveAccount')} <Link to="/login">{t('register.login')}</Link>
        </>
      }
    >
      <form noValidate onSubmit={(event: FormEvent) => event.preventDefault()}>
        {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
        <FormSection title={t('register.sectionIdentity')}>
          <TextField
            label={t('fields.fullName')}
            name="full_name"
            autoComplete="name"
            leading={<Icon name="user" size={18} />}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            error={errors.fieldErrors.full_name}
            required
          />
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
          <TextField
            label={t('fields.phone')}
            optional
            type="tel"
            name="phone_number"
            autoComplete="tel"
            inputMode="tel"
            dir="ltr"
            leading={<Icon name="phone" size={18} />}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            error={errors.fieldErrors.phone_number}
          />
          <Select
            label={t('fields.role')}
            name="role"
            hint={t('register.roleHint')}
            value={role}
            onChange={(e) => setRole(e.target.value as Exclude<AccountRole, 'ADMIN'>)}
            error={errors.fieldErrors.role}
          >
            {SELF_REGISTRATION_ROLES.map((code) => (
              <option key={code} value={code}>
                {t(`roles.${code}`)}
              </option>
            ))}
          </Select>
        </FormSection>
        <FormSection title={t('register.sectionSecurity')}>
          <PasswordField
            label={t('fields.password')}
            name="password"
            autoComplete="new-password"
            dir="ltr"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.fieldErrors.password}
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
        </FormSection>
        <FormActions>
          <ApiActionButton
            type="submit"
            size="lg"
            action={submit}
            onSuccess={() => navigate(DEFAULT_AUTHENTICATED_PATH, { replace: true })}
            onError={onError}
            pendingLabel={t('register.submitting')}
          >
            {t('register.submit')}
          </ApiActionButton>
        </FormActions>
      </form>
    </AuthShell>
  )
}

export function PasswordRules() {
  const { t } = useTranslation()
  return (
    <details>
      <summary>{t('passwordRules.title')}</summary>
      <ul>
        <li>{t('passwordRules.min')}</li>
        <li>{t('passwordRules.notCommon')}</li>
        <li>{t('passwordRules.notNumeric')}</li>
        <li>{t('passwordRules.notSimilar')}</li>
      </ul>
    </details>
  )
}
