import { describe, expect, it } from 'vitest'

import ar from '../i18n/locales/ar.json'
import en from '../i18n/locales/en.json'
import { PROFESSION_GROUPS, PROFESSIONS } from './jobs.types'

describe('profession taxonomy (mirror of apps/jobs/types.py)', () => {
  it('lists healthcare first, then every other field, each profession once', () => {
    expect(PROFESSION_GROUPS.map(([g]) => g)).toEqual([
      'HEALTHCARE',
      'HEALTH_BUSINESS',
      'TECHNOLOGY',
      'BUSINESS',
      'EDUCATION',
      'OTHER_FIELDS',
    ])
    expect(new Set(PROFESSIONS).size).toBe(PROFESSIONS.length)
    expect(PROFESSIONS[0]).toBe('DOCTOR')
    for (const p of ['SOFTWARE_DEVELOPER', 'CYBERSECURITY', 'ACCOUNTANT', 'SALES', 'HUMAN_RESOURCES', 'BIOMEDICAL_ENGINEER', 'TEACHER', 'MANAGER']) {
      expect(PROFESSIONS).toContain(p)
    }
  })

  it('has an Arabic and English label for every profession and group', () => {
    for (const p of PROFESSIONS) {
      expect((en.professions as Record<string, string>)[p], p).toBeTruthy()
      expect((ar.professions as Record<string, string>)[p], p).toBeTruthy()
    }
    for (const [g] of PROFESSION_GROUPS) {
      expect((en.professionGroups as Record<string, string>)[g], g).toBeTruthy()
      expect((ar.professionGroups as Record<string, string>)[g], g).toBeTruthy()
    }
    // and nothing the web labels is unknown to the taxonomy
    expect(Object.keys(en.professions).sort()).toEqual([...PROFESSIONS].sort())
  })
})
