import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { auth as authApi, type Account, type PreferredLanguage } from '../api'
import { useAuth } from '../auth/useAuth'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Avatar,
  Badge,
  Button,
  Container,
  FormActions,
  Icon,
  PageHeader,
  PageStack,
  SectionCard,
  Select,
  TextField,
  useFormErrors,
} from '../design-system'
import { changeLanguage, isLanguage } from '../i18n'
import styles from './ProfilePage.module.css'
import { ClientValidationError, isPhone } from './validation'

/**
 * /profile — identity comes exclusively from GET /api/v1/me (loaded fresh
 * through AsyncPage). Only the fields PATCH /me accepts are editable.
 * Role and capabilities are displayed as hints; the backend enforces them.
 */
export function ProfilePage() {
  const { t } = useTranslation()
  const { refreshAccount } = useAuth()
  return (
    <Container>
      <PageHeader eyebrow={<><Icon name="user" size={16} />{t('nav.profile')}</>} title={t('profile.title')} />
      <AsyncPage load={() => refreshAccount()}>
        {(account, reload) => <ProfileView account={account} reload={reload} />}
      </AsyncPage>
    </Container>
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
    <PageStack>
      <SectionCard title={t('profile.overviewTitle')} headingLevel={2} actions={<Button variant="ghost" size="sm" onClick={reload} leading={<Icon name="refresh" size={16} />}>{t('common.retry')}</Button>}>
        <div className={styles.overview}>
          <Avatar name={account.full_name} size="xl" />
          <div className={styles.overviewText}>
            <p className={styles.overviewName}>{account.full_name}</p>
            <p className="text-secondary ltr">{account.email}</p>
            <div className={styles.overviewMeta}>
              <Badge tone="brand">{t(`roles.${account.role}`)}</Badge>
              {account.email_verified ? (
                <Badge tone="success" leading={<Icon name="shieldCheck" size={12} />}>
                  {t('profile.emailVerified')}
                </Badge>
              ) : (
                <Badge tone="warning">{t('profile.emailNotVerified')}</Badge>
              )}
            </div>
          </div>
        </div>
      </SectionCard>

      <div className={styles.grid}>
        <PageStack>
          <SectionCard title={t('profile.contactTitle')} description={t('profile.contactBody')} headingLevel={2}>
            <form noValidate onSubmit={(event) => event.preventDefault()}>
              {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
              {saved ? <Alert kind="success">{t('profile.saved')}</Alert> : null}
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
                leading={<Icon name="phone" size={18} />}
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                error={errors.fieldErrors.phone_number}
              />
              <Select
                label={t('fields.preferredLanguage')}
                name="preferred_language"
                value={language}
                onChange={(e) => setLanguage(e.target.value as PreferredLanguage)}
              >
                <option value="ar">العربية</option>
                <option value="en">English</option>
              </Select>
              <FormActions>
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
              </FormActions>
            </form>
          </SectionCard>

          <SectionCard title={t('profile.capabilities')} description={t('profile.capabilitiesBody')} headingLevel={2}>
            <ul className={styles.chips} aria-label={t('profile.capabilities')}>
              {account.permissions.map((code) => (
                <li key={code}>
                  <Badge tone="outline" className={styles.mono}>
                    <span className="ltr">{code}</span>
                  </Badge>
                </li>
              ))}
            </ul>
          </SectionCard>
        </PageStack>

        <PageStack>
          <SectionCard title={t('profile.accountTitle')} headingLevel={2}>
            <dl className={styles.facts}>
              <dt>{t('fields.email')}</dt>
              <dd className="ltr">{account.email}</dd>
              <dt>{t('profile.role')}</dt>
              <dd>{t(`roles.${account.role}`)}</dd>
              <dt>{t('profile.memberSince')}</dt>
              <dd>{new Date(account.created_at).toLocaleDateString(i18n.language)}</dd>
              {account.last_login ? (
                <>
                  <dt>{t('profile.lastLogin')}</dt>
                  <dd>{new Date(account.last_login).toLocaleString(i18n.language)}</dd>
                </>
              ) : null}
            </dl>
          </SectionCard>

          <SectionCard title={t('profile.securityTitle')} headingLevel={2}>
            <dl className={styles.facts}>
              <dt>{t('profile.identity')}</dt>
              <dd>
                {account.email_verified ? (
                  <Badge tone="success" leading={<Icon name="shieldCheck" size={12} />}>
                    {t('profile.emailVerified')}
                  </Badge>
                ) : (
                  <Badge tone="warning">{t('profile.emailNotVerified')}</Badge>
                )}
              </dd>
              <dt>{t('profile.passwordLabel')}</dt>
              <dd>{account.has_password ? t('profile.passwordSet') : t('profile.noPassword')}</dd>
            </dl>
            {!account.email_verified ? (
              <FormActions>
                {verificationSent ? (
                  <Alert kind="success">{t('profile.verificationSent')}</Alert>
                ) : (
                  <ApiActionButton
                    variant="secondary"
                    action={() => authApi.requestEmailVerification()}
                    onSuccess={() => setVerificationSent(true)}
                    onError={(error) => errors.applyApiError(error)}
                    pendingLabel={t('profile.sendingVerification')}
                    leading={<Icon name="mail" size={18} />}
                  >
                    {t('profile.sendVerification')}
                  </ApiActionButton>
                )}
              </FormActions>
            ) : null}
          </SectionCard>
        </PageStack>
      </div>
    </PageStack>
  )
}
