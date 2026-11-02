import { describe, expect, it } from 'vitest'

import { PHONE_MAX_DIGITS, toPhoneDigits } from './phone'

describe('phone input', () => {
  it('keeps digits only and never more than 11', () => {
    expect(toPhoneDigits('313131323133213123')).toBe('31313132313')
    expect(toPhoneDigits('0770 123-4567 99')).toBe('07701234567')
    expect(toPhoneDigits('07a7b0')).toBe('0770')
    expect(PHONE_MAX_DIGITS).toBe(11)
  })

  it('turns an international prefix into the national 0', () => {
    expect(toPhoneDigits('+964 770 123 4567')).toBe('07701234567')
    expect(toPhoneDigits('009647701234567')).toBe('07701234567')
    expect(toPhoneDigits('9647701234567')).toBe('07701234567')
  })
})
