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

describe('Arabic plurals in the store', () => {
  it('product and cart counts never fall back to the raw key', async () => {
    initI18n()
    await changeLanguage('ar')
    for (const count of [0, 1, 2, 5, 11, 28, 100]) {
      for (const key of ['store.count', 'store.inCartCount', 'store.cartCountLabel', 'store.cartSummary']) {
        expect(i18n.t(key, { count }), `${key} ${count}`).not.toMatch(/store\.|products|items|cart/i)
      }
    }
    expect(i18n.t('store.count', { count: 28 })).toBe('28 منتجاً')
  })
})
