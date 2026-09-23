/** 4px base scale. Values in px; CSS uses rem equivalents (16px root). */
export const space = {
  0: 0,
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 20,
  6: 24,
  8: 32,
  10: 40,
  12: 48,
  16: 64,
  20: 80,
} as const

export const contentWidth = {
  sm: 640,
  md: 880,
  lg: 1120,
  xl: 1280,
} as const

/** Vertical rhythm between page sections (mobile / desktop). */
export const sectionSpace = { mobile: 40, desktop: 64 } as const

/** Horizontal page gutter (mobile / desktop). */
export const gutter = { mobile: 16, desktop: 32 } as const
