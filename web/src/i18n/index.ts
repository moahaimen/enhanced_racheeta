/**
 * Localisation. Arabic (RTL) is the default; English is ready.
 * Changing the language also flips `<html dir>` so the whole layout mirrors.
 */
import i18next from 'i18next'
import { initReactI18next } from 'react-i18next'

import ar from './locales/ar.json'
import en from './locales/en.json'

export const SUPPORTED_LANGUAGES = ['ar', 'en'] as const
export type Language = (typeof SUPPORTED_LANGUAGES)[number]
export const DEFAULT_LANGUAGE: Language = 'ar'
const STORAGE_KEY = 'racheeta.language'

export function isLanguage(value: unknown): value is Language {
  return typeof value === 'string' && (SUPPORTED_LANGUAGES as readonly string[]).includes(value)
}

function readStoredLanguage(): Language {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return isLanguage(stored) ? stored : DEFAULT_LANGUAGE
  } catch {
    return DEFAULT_LANGUAGE
  }
}

export function applyDocumentDirection(language: Language): void {
  const dir = i18next.dir(language)
  document.documentElement.setAttribute('dir', dir)
  document.documentElement.setAttribute('lang', language)
}

export async function changeLanguage(language: Language): Promise<void> {
  await i18next.changeLanguage(language)
  try {
    window.localStorage.setItem(STORAGE_KEY, language)
  } catch {
    /* storage unavailable (private mode); language still applies for this session */
  }
}

export function initI18n(): typeof i18next {
  if (!i18next.isInitialized) {
    void i18next.use(initReactI18next).init({
      resources: { ar: { translation: ar }, en: { translation: en } },
      lng: readStoredLanguage(),
      fallbackLng: 'en',
      supportedLngs: [...SUPPORTED_LANGUAGES],
      interpolation: { escapeValue: false },
      returnNull: false,
    })
    applyDocumentDirection(i18next.language as Language)
    i18next.on('languageChanged', (lng) => {
      if (isLanguage(lng)) applyDocumentDirection(lng)
    })
  }
  return i18next
}

export default i18next
