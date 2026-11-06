import { useTranslation } from 'react-i18next'

/** Whole Iraqi dinars, formatted for the current language (amounts always come from the server). */
export function useMoney() {
  const { i18n } = useTranslation()
  return (value: string | number | null | undefined, currency = 'IQD') =>
    `${Math.round(Number(value ?? 0)).toLocaleString(i18n.language)} ${currency === 'IQD' ? (i18n.language.startsWith('ar') ? 'د.ع' : 'IQD') : currency}`
}

export function newIdempotencyKey(): string {
  const c = globalThis.crypto
  if (c && typeof c.randomUUID === 'function') return c.randomUUID()
  return `k-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}
