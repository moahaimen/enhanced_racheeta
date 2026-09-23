/** px. Controls are moderate, cards larger, hero blocks premium; never all-pill. */
export const radius = { sm: 8, md: 12, lg: 16, xl: 24, full: 999 } as const
export const radiusRoles = {
  control: radius.md,
  card: radius.lg,
  hero: radius.xl,
  badge: radius.full,
} as const
