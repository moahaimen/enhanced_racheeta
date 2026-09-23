import { describe, expect, it } from 'vitest'

import i18n, { changeLanguage, initI18n } from './index'

describe('i18n direction', () => {
  it('defaults to Arabic and RTL', async () => {
    initI18n()
    await changeLanguage('ar')
    expect(i18n.language).toBe('ar')
    expect(document.documentElement.getAttribute('dir')).toBe('rtl')
    expect(document.documentElement.getAttribute('lang')).toBe('ar')
    expect(i18n.t('app.name')).toBe('رشيتة')
  })

  it('switches to English and LTR, and persists the choice', async () => {
    initI18n()
    await changeLanguage('en')
    expect(document.documentElement.getAttribute('dir')).toBe('ltr')
    expect(document.documentElement.getAttribute('lang')).toBe('en')
    expect(i18n.t('app.name')).toBe('Racheeta')
    expect(window.localStorage.getItem('racheeta.language')).toBe('en')
    await changeLanguage('ar')
  })
})
