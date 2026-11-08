import { describe, expect, it } from 'vitest'

import en from '../../../i18n/locales/en.json'
import { iconNames } from '../../icons'
import { professionIcon } from './professionIcon'

describe('professionIcon', () => {
  it('gives every known profession its own existing icon (never the generic fallback)', () => {
    for (const profession of Object.keys(en.professions)) {
      const icon = professionIcon(profession)
      expect(iconNames, profession).toContain(icon)
      // only the medical representative uses the briefcase on purpose
      expect(icon === 'briefcase' && profession !== 'MEDICAL_REPRESENTATIVE', profession).toBe(false)
    }
  })

  it('falls back to a briefcase for an unknown value', () => {
    expect(professionIcon('SOMETHING_NEW')).toBe('briefcase')
  })
})
