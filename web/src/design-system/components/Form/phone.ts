/** Iraqi national phone numbers are at most 11 digits (07XX XXX XXXX). */
export const PHONE_MAX_DIGITS = 11

/**
 * What a phone field may contain while typing: digits only, at most 11. A pasted or typed
 * international prefix (+964 / 00964 / 964) becomes the national leading 0.
 */
export function toPhoneDigits(value: string): string {
  let digits = value.replace(/\D/g, '')
  if (value.trim().startsWith('+964') || digits.startsWith('00964')) digits = '0' + digits.replace(/^(00)?964/, '')
  else if (digits.startsWith('964') && digits.length > 11) digits = '0' + digits.slice(3)
  return digits.slice(0, PHONE_MAX_DIGITS)
}

