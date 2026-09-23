import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { auth as authApi, type Account, type PreferredLanguage } from '../api'
import { useAuth } from '../auth/useAuth'
import { ApiActionButton, AsyncPage } from '../components'
import { FormAlert, TextField, useFormErrors } from '../components/forms'
import { changeLanguage, isLanguage } from '../i18n'
import { ClientValidationError, isPhone } from './validation'

/**
 * /profile — identity comes exclusively from GET /api/v1/me (loaded fresh
 * through AsyncPage). Only the fields PATCH /me accepts are editable.
 * Role and capabilities are displayed as hints; the backend enforces them.
 */
export function ProfilePage() {
  const { refreshAccount } = useAuth()
  return (
    <AsyncPage load={() => refreshAccount()}>
      {(account, reload) => <ProfileView account={account} reload={reload} />}
    </AsyncPage>
  )
}

const FIELDS = ['full_name', 'phone_number', 'preferred_language'] as const

function ProfileView({ account, reload }: { account: Account; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const { updateAccount } = useAuth()
  const [fullName, setFullName] = useState(account.full_name)
  const [phone, setPhone] = useState(account.phone_number)
  const [language, setLanguage] = useState<PreferredLanguage>(account.preferred_language)
  const [saved, setSaved] = useState(false)
  const [verificationSent, setVerificationSent] = useState(false)
  const errors = useFormErrors(FIELDS)

  const save = async () => {
    setSaved(false)
    const next: Partial<Record<(typeof FIELDS)[number], string>> = {}
    if (!fullName.trim()) next.full_name = t('validation.required')
    if (phone.trim() && !isPhone(phone)) next.phone_number = t('validation.phone')
    errors.setFieldErrors(next)
    errors.setFormError(null)
    if (Object.keys(next).length > 0) throw new ClientValidationError()
    return updateAccount({
      full_name: fullName.trim(),
      phone_number: phone.replace(/[\s-]/g, ''),
      preferred_language: language,
    })
  }

  const onSaved = async (updated: Account) => {
    setSaved(true)
    if (isLanguage(updated.preferred_language) && updated.preferred_language !== i18n.language) {
      await changeLanguage(updated.preferred_language)
    }
  }

  return (
    <>
      <section className="card">
        <h2>{t('profile.title')}</h2>
        <dl className="status">
          <dt>{t('fields.email')}</dt>
          <dd dir="ltr">{account.email}</dd>
          <dt>{t('profile.role')}</dt>
          <dd>
            <span className="badge">{t(`roles.${account.role}`)}</span>
          </dd>
          <dt>{t('profile.memberSince')}</dt>
          <dd>{new Date(account.created_at).toLocaleDateString(i18n.language)}</dd>
          <dt>{t('profile.identity')}</dt>
          <dd>
            {account.email_verified ? (
              <span className="badge badge--ok">{t('profile.emailVerified')}</span>
            ) : (
              <span className="badge badge--warn">{t('profile.emailNotVerified')}</span>
            )}
          </dd>
        </dl>
        {!account.email_verified ? (
          <div className="actions">
            {verificationSent ? (
              <FormAlert kind="success">{t('profile.verificationSent')}</FormAlert>
            ) : (
              <ApiActionButton
                className="btn--ghost"
                action={() => authApi.requestEmailVerification()}
                onSuccess={() => setVerificationSent(true)}
                onError={(error) => errors.applyApiError(error)}
                pendingLabel={t('profile.sendingVerification')}
              >
                {t('profile.sendVerification')}
              </ApiActionButton>
            )}
          </div>
        ) : null}
        {!account.has_password ? <p className="muted">{t('profile.noPassword')}</p> : null}
      </section>

      <section className="card card--form">
        <h3>{t('profile.edit')}</h3>
        <form noValidate onSubmit={(event) => event.preventDefault()}>
          {errors.formError ? <FormAlert kind="error">{errors.formError}</FormAlert> : null}
          {saved ? <FormAlert kind="success">{t('profile.saved')}</FormAlert> : null}
          <TextField
            label={t('fields.fullName')}
            name="full_name"
            autoComplete="name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            error={errors.fieldErrors.full_name}
            required
          />
          <TextField
            label={t('fields.phone')}
            type="tel"
            name="phone_number"
            autoComplete="tel"
            dir="ltr"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            error={errors.fieldErrors.phone_number}
          />
          <div className="field">
            <label className="field__label" htmlFor="profile-language">
              {t('fields.preferredLanguage')}
            </label>
            <div className="field__control">
              <select
                id="profile-language"
                name="preferred_language"
                className="field__input"
                value={language}
                onChange={(e) => setLanguage(e.target.value as PreferredLanguage)}
              >
                <option value="ar">العربية</option>
                <option value="en">English</option>
              </select>
            </div>
          </div>
          <div className="form__actions">
            <ApiActionButton
              type="submit"
              action={save}
              onSuccess={onSaved}
              onError={(error) => {
                if (!(error instanceof ClientValidationError)) errors.applyApiError(error)
              }}
              pendingLabel={t('common.saving')}
            >
              {t('common.save')}
            </ApiActionButton>
            <button type="button" className="btn btn--ghost" onClick={reload}>
              {t('common.retry')}
            </button>
          </div>
        </form>
      </section>

      <section className="card">
        <h3>{t('profile.capabilities')}</h3>
        <ul className="chips" aria-label={t('profile.capabilities')}>
          {account.permissions.map((code) => (
            <li key={code} className="chip" dir="ltr">
              {code}
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}
