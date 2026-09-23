/** px; min-width queries. */
export const breakpoint = { sm: 480, md: 768, lg: 1024, xl: 1280 } as const
export const mediaQuery = {
  sm: `(min-width: ${breakpoint.sm}px)`,
  md: `(min-width: ${breakpoint.md}px)`,
  lg: `(min-width: ${breakpoint.lg}px)`,
  xl: `(min-width: ${breakpoint.xl}px)`,
} as const
