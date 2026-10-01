import type { TFunction } from 'i18next'

import { ApiError } from '../../api'
import { toErrorMessage } from '../../hooks/useAsync'

const DECIMAL_STRING = /^([+-]?)(\d+)(?:\.(\d+))?$/

/**
 * A backend Decimal string, locale-formatted EXACTLY. The amount is never converted to a JavaScript
 * `number` (IEEE-754 would turn 98999999999999.01 into ...02): the integer digits are grouped through
 * `BigInt`, the fraction digits are kept as given (trailing zeros included) and localised one digit at a
 * time, and the locale's own decimal separator comes from Intl. A malformed value is shown as received
 * rather than corrupted or thrown from render.
 */
export function formatMoney(amount: string, currency: string, language: string): string {
  const match = DECIMAL_STRING.exec(amount.trim())
  if (!match) return `${amount} ${currency}`
  const [, sign, whole = '0', fraction = ''] = match
  try {
    const integer = new Intl.NumberFormat(language, { useGrouping: true, maximumFractionDigits: 0 }).format(BigInt(whole))
    const digit = new Intl.NumberFormat(language, { useGrouping: false, maximumFractionDigits: 0 })
    const separator = new Intl.NumberFormat(language).formatToParts(1.1).find((part) => part.type === 'decimal')?.value ?? '.'
    // Number() below is applied to ONE character '0'..'9' only, never to the monetary value.
    const localFraction = [...fraction].map((d) => digit.format(Number(d))).join('')
    return `${sign === '-' ? '-' : ''}${integer}${fraction ? separator + localFraction : ''} ${currency}`
  } catch {
    return `${amount} ${currency}`
  }
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
