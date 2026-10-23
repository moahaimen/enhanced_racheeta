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

describe('pickScript', () => {
  it('shows the half of "Arabic | English" that matches the UI language', async () => {
    const { pickScript } = await import('./localized')
    expect(pickScript('د. كريم الساعدي | Dr. Karim Al-Saadi', 'ar')).toBe('د. كريم الساعدي')
    expect(pickScript('د. كريم الساعدي | Dr. Karim Al-Saadi', 'en')).toBe('Dr. Karim Al-Saadi')
    expect(pickScript('Dr. Karim Al-Saadi | د. كريم', 'ar')).toBe('د. كريم')
  })

  it('leaves everything else untouched', async () => {
    const { pickScript } = await import('./localized')
    for (const text of ['مستشفى دجلة', 'Dijla Hospital', 'A | B', 'عيادة | مركز', 'a | b | c', '']) {
      expect(pickScript(text, 'ar')).toBe(text)
      expect(pickScript(text, 'en')).toBe(text)
    }
  })
})
