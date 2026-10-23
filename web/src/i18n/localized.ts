import { useTranslation } from 'react-i18next'

interface Bilingual {
  name_ar: string
  name_en: string
}

/** Picks the name in the active UI language; English falls back to Arabic and vice versa. */
export function localizedName(item: Bilingual | null | undefined, language: string): string {
  if (!item) return ''
  return language.startsWith('ar') ? item.name_ar || item.name_en : item.name_en || item.name_ar
}

export function useLocalizedName(): (item: Bilingual | null | undefined) => string {
  const { i18n } = useTranslation()
  return (item) => localizedName(item, i18n.language)
}

const ARABIC = /[؀-ۿ]/

/**
 * Free-text fields (provider, job, listing, product names) are single-language in the API. When an
 * administrator or seller writes "العربية | English", show the half that matches the UI language so
 * a card never wraps both. Text without that exact shape is returned unchanged.
 */
export function pickScript(text: string, language: string): string {
  const parts = text.split(' | ')
  if (parts.length !== 2) return text
  const [first, second] = parts.map((part) => part.trim())
  if (!first || !second || ARABIC.test(first) === ARABIC.test(second)) return text
  const arabicPart = ARABIC.test(first) ? first : second
  const otherPart = arabicPart === first ? second : first
  return language.startsWith('ar') ? arabicPart : otherPart
}

export function useScriptText(): (text: string) => string {
  const { i18n } = useTranslation()
  return (text) => pickScript(text, i18n.language)
}
