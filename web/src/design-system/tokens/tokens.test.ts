import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { duration, neutral, radius, semantic, shadow, teal } from './index'

/** tokens.css must mirror the TypeScript token values (single source of truth). */
const css = readFileSync(resolve(process.cwd(), 'src/design-system/styles/tokens.css'), 'utf8')

function cssVar(name: string): string | undefined {
  const match = css.match(new RegExp(`--${name}:\\s*([^;]+);`))
  return match?.[1]?.trim()
}

describe('design tokens', () => {
  it('teal scale matches CSS', () => {
    for (const [step, value] of Object.entries(teal)) expect(cssVar(`color-primary-${step}`)).toBe(value)
  })

  it('neutral scale matches CSS', () => {
    for (const [step, value] of Object.entries(neutral)) expect(cssVar(`color-neutral-${step}`)).toBe(value)
  })

  it('semantic colours match CSS', () => {
    expect(cssVar('color-success')).toBe(semantic.success)
    expect(cssVar('color-warning')).toBe(semantic.warning)
    expect(cssVar('color-error')).toBe(semantic.error)
    expect(cssVar('color-info')).toBe(semantic.info)
    expect(cssVar('color-error-soft')).toBe(semantic.errorSoft)
  })

  it('shadows, radius and motion match CSS', () => {
    expect(cssVar('shadow-sm')).toBe(shadow.sm)
    expect(cssVar('shadow-md')).toBe(shadow.md)
    expect(cssVar('radius-lg')).toBe(`${radius.lg / 16}rem`)
    expect(cssVar('duration-base')).toBe(`${duration.base}ms`)
  })

  it('exposes role tokens for theming', () => {
    for (const name of ['surface-primary', 'surface-secondary', 'text-primary', 'text-secondary', 'border-subtle', 'radius-card', 'shadow-card', 'space-section']) {
      expect(cssVar(name), name).toBeDefined()
    }
  })
})
