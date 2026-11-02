export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
export const PHONE_RE = /^\+?[0-9]{7,15}$/
export const PASSWORD_MIN_LENGTH = 8

export function isEmail(value: string): boolean {
  return EMAIL_RE.test(value.trim())
}

export function isPhone(value: string): boolean {
  return PHONE_RE.test(value.replace(/[\s-]/g, ''))
}

/** Thrown by submit handlers when client validation fails; not an API error. */
export class ClientValidationError extends Error {
  constructor() {
    super('client validation failed')
    this.name = 'ClientValidationError'
  }
}

/**
 * Iraqi phone numbers — the same rule as the server (backend/apps/core/phone.py).
 * Mobile 07[3-9]X XXX XXXX; landline 0[1-6]... (9-10 digits); +964 / 00964 / 964 accepted.
 * Returns the national form ("07701234567") or null when invalid. Empty input returns "".
 */
export function normalizeIraqiPhone(value: string, { mobileOnly = false } = {}): string | null {
  let raw = value.replace(/[\s\-().]/g, '')
  if (raw === '') return ''
  if (raw.startsWith('+964')) raw = '0' + raw.slice(4)
  else if (raw.startsWith('00964')) raw = '0' + raw.slice(5)
  else if (raw.startsWith('964') && raw.length >= 12) raw = '0' + raw.slice(3)
  if (/^07[3-9]\d{8}$/.test(raw)) return raw
  if (!mobileOnly && /^0[1-6]\d{7,8}$/.test(raw)) return raw
  return null
}

export function isIraqiPhone(value: string, options: { mobileOnly?: boolean } = {}): boolean {
  return normalizeIraqiPhone(value, options) !== null
}

/** Keep only what a phone number can contain while typing: digits, spaces and one leading "+". */
export function sanitizePhoneInput(value: string): string {
  const plus = value.trimStart().startsWith('+') ? '+' : ''
  return plus + value.replace(/[^\d ]/g, '').replace(/ {2,}/g, ' ').trimStart()
}

/** Digits only (whole numbers such as stock, minutes). */
export function digitsOnly(value: string): string {
  return value.replace(/\D/g, '')
}

/** A non-negative decimal while typing (prices, areas): digits and one dot. */
export function decimalOnly(value: string): string {
  const cleaned = value.replace(/[^\d.]/g, '')
  const [whole, ...rest] = cleaned.split('.')
  return rest.length ? `${whole}.${rest.join('')}` : whole ?? ''
}

/** A person's name: at least 2 characters and some letters (same rule as the server). */
export function isFullName(value: string): boolean {
  const v = value.trim().replace(/\s+/g, ' ')
  return v.length >= 2 && /\p{L}/u.test(v)
}
