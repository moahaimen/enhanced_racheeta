import { describe, expect, it } from 'vitest'

import { decimalOnly, digitsOnly, isIraqiPhone, normalizeIraqiPhone, sanitizePhoneInput } from './validation'

describe('Iraqi phone numbers (same rule as the server)', () => {
  it.each([
    ['07701234567', '07701234567'],
    ['0770 123 4567', '07701234567'],
    ['+964 770 123 4567', '07701234567'],
    ['009647801234567', '07801234567'],
    ['01 234 5678', '012345678'],
  ])('accepts %s', (raw, expected) => {
    expect(normalizeIraqiPhone(raw)).toBe(expected)
  })

  it.each(['0770123456', '07001234567', '0770abc4567', '+1 202 555 0100', '12345'])('rejects %s', (raw) => {
    expect(isIraqiPhone(raw)).toBe(false)
  })

  it('refuses a landline where a mobile is required', () => {
    expect(isIraqiPhone('012345678', { mobileOnly: true })).toBe(false)
  })

  it('input helpers keep only what the field may contain', () => {
    expect(sanitizePhoneInput('+964 77a0-12')).toBe('+964 77012')
    expect(digitsOnly('12a3')).toBe('123')
    expect(decimalOnly('1a2.5.0')).toBe('12.50')
  })
})
