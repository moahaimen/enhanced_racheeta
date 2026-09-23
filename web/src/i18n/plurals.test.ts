import { describe, expect, it } from 'vitest'

import i18n, { changeLanguage, initI18n } from './index'

/** Arabic has six plural categories; every pluralised key must define them. */
describe('Arabic plurals', () => {
  it('formats result counts in Arabic for every category', async () => {
    initI18n()
    await changeLanguage('ar')
    for (const count of [0, 1, 2, 5, 11, 100]) {
      const text = i18n.t('providers.results', { count })
      expect(text, `count ${count}`).not.toMatch(/result/i)
    }
    expect(i18n.t('providers.results', { count: 5 })).toBe('5 نتائج')
    expect(i18n.t('providers.results', { count: 0 })).toBe('لا توجد نتائج')
  })
})
