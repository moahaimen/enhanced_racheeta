import type { TFunction } from 'i18next'

import { ApiError } from '../../api'
import { toErrorMessage } from '../../hooks/useAsync'

export function formatMoney(amount: string, currency: string, language: string): string {
  return `${Number(amount).toLocaleString(language)} ${currency}`
}

/** Both dates given and the end is not before the start: the only condition to ask the backend for a preview. */
export function isDateRange(starts: string, ends: string): boolean {
  return starts !== '' && ends !== '' && ends >= starts
}

/**
 * A backend refusal in the user's language: every typed per-field code (`apiErrors.<code>`), not just the
 * first, then the typed error code itself. English server messages are never parsed.
 */
export function refusalMessage(error: unknown, t: TFunction): string {
  if (error instanceof ApiError && error.code === 'validation_error' && error.codes) {
    const seen = new Set<string>()
    for (const codes of Object.values(error.codes)) {
      for (const code of codes) {
        const text = t(`apiErrors.${code}`, { defaultValue: '' })
        if (text) seen.add(text)
      }
    }
    if (seen.size > 0) return [...seen].join(' ')
  }
  return toErrorMessage(error)
}
