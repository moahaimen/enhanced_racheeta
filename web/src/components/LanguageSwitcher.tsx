import { useTranslation } from 'react-i18next'

import { SUPPORTED_LANGUAGES, changeLanguage, isLanguage } from '../i18n'

const LABELS: Record<string, string> = { ar: 'العربية', en: 'English' }

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation()
  return (
    <label className="lang-switch">
      <span className="visually-hidden">{t('common.language')}</span>
      <select
        value={i18n.language}
        onChange={(event) => {
          const next = event.target.value
          if (isLanguage(next)) void changeLanguage(next)
        }}
      >
        {SUPPORTED_LANGUAGES.map((code) => (
          <option key={code} value={code}>
            {LABELS[code]}
          </option>
        ))}
      </select>
    </label>
  )
}
