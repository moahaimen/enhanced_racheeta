import { describe, expect, it } from 'vitest'

import { formatMoney } from './advertisingFormat'

describe('formatMoney keeps backend decimal strings exact', () => {
  it('shows the exact cents of the amount a float would corrupt (the reviewed case)', () => {
    expect(Number('98999999999999.01').toLocaleString('en', { minimumFractionDigits: 2 })).toContain('.02') // the bug being prevented
    const text = formatMoney('98999999999999.01', 'IQD', 'en')
    expect(text).toBe('98,999,999,999,999.01 IQD')
    expect(text).not.toContain('98,999,999,999,999.02')
  })

  it('keeps the maximum supported amount exactly', () => {
    expect(formatMoney('99999999999999.99', 'IQD', 'en')).toBe('99,999,999,999,999.99 IQD')
  })

  it('keeps trailing zeros: the exactly-fitting 100-day boundary stays .00', () => {
    expect(formatMoney('99999999999999.00', 'IQD', 'en')).toBe('99,999,999,999,999.00 IQD')
    expect(formatMoney('10000.00', 'IQD', 'en')).toBe('10,000.00 IQD')
  })

  it('keeps small cents and a lone trailing zero', () => {
    expect(formatMoney('0.01', 'USD', 'en')).toBe('0.01 USD')
    expect(formatMoney('1.10', 'USD', 'en')).toBe('1.10 USD')
    expect(formatMoney('1234.56', 'USD', 'en')).toBe('1,234.56 USD')
    expect(formatMoney('1000.00', 'IQD', 'en')).toBe('1,000.00 IQD')
  })

  it('handles a whole number, leading zeros and an optional sign', () => {
    expect(formatMoney('5', 'IQD', 'en')).toBe('5 IQD')
    expect(formatMoney('007.50', 'IQD', 'en')).toBe('7.50 IQD')
    expect(formatMoney('-1234.50', 'IQD', 'en')).toBe('-1,234.50 IQD')
  })

  it('is exact in Arabic too, using the locale\'s own grouping, digits and separator', () => {
    const intl = new Intl.NumberFormat('ar')
    const digit = (d: number) => new Intl.NumberFormat('ar', { useGrouping: false }).format(d)
    const separator = intl.formatToParts(1.1).find((p) => p.type === 'decimal')?.value ?? '.'
    const text = formatMoney('98999999999999.01', 'IQD', 'ar')
    expect(text).toBe(`${intl.format(98999999999999n)}${separator}${digit(0)}${digit(1)} IQD`)
    expect(text.endsWith(`${digit(0)}${digit(1)} IQD`)).toBe(true) // fraction is exactly "01"
    expect(text).not.toContain(`${separator}${digit(0)}${digit(2)}`) // never ".02"
    expect(formatMoney('99999999999999.00', 'IQD', 'ar')).toContain(`${separator}${digit(0)}${digit(0)}`)
  })

  it('shows a malformed value as received instead of corrupting it or throwing', () => {
    for (const bad of ['', 'abc', '1,000.00', '1e5', '12.', '.5', 'NaN', '1.2.3']) {
      expect(() => formatMoney(bad, 'IQD', 'en')).not.toThrow()
      expect(formatMoney(bad, 'IQD', 'en')).toBe(`${bad} IQD`)
    }
  })
})
