import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { PROFESSION_ICON, professionIcon } from '../design-system/components/JobCard/professionIcon'
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

  it('matches the server vocabulary in docs/api/openapi.yaml (ProfessionEnum)', () => {
    // The OpenAPI file is generated from apps/jobs/types.py and CI fails when it is stale, so a
    // profession added on the server without this mirror (or the reverse) fails here.
    const yaml = readFileSync(resolve(process.cwd(), '../docs/api/openapi.yaml'), 'utf8')
    const block = yaml.split('\n    ProfessionEnum:\n')[1]!.split('\n      type: string')[0]!
    const server = [...block.matchAll(/^ {6}- (\w+)$/gm)].map((m) => m[1])
    expect(server.length).toBeGreaterThan(0)
    expect([...PROFESSIONS].sort()).toEqual([...server].sort())
  })

  it('chooses an icon for every profession (the fallback is for unknown values only)', () => {
    expect(Object.keys(PROFESSION_ICON).sort()).toEqual([...PROFESSIONS].sort())
    expect(professionIcon('NOT_A_PROFESSION')).toBe('briefcase')
  })
})
