/** ms. Subtle only; prefers-reduced-motion disables transitions globally. */
export const duration = { fast: 120, base: 180, slow: 260 } as const
export const easing = {
  standard: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
  emphasized: 'cubic-bezier(0.3, 0, 0, 1)',
} as const
