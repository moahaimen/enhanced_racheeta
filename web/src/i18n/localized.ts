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
