/**
 * Racheeta colour tokens. Source of truth for the values; `tokens.css`
 * exposes the same values as CSS custom properties (a test keeps them equal).
 */
export const teal = {
  50: '#e0f1f0',
  100: '#d1e2e5',
  200: '#b1d3d7',
  300: '#85c3c3',
  400: '#56aaac',
  500: '#3e9c9e',
  600: '#148283',
  700: '#148283',
  800: '#0f6872',
  900: '#0b4f56',
} as const

export const neutral = {
  0: '#ffffff',
  50: '#f3f5f7',
  100: '#e9eef2',
  200: '#dddfe4',
  300: '#c9cdd3',
  400: '#9a9ea3',
  500: '#78797a',
  600: '#575859',
  700: '#403e3f',
  800: '#363433',
  900: '#161616',
} as const

export const semantic = {
  success: '#148283',
  successSoft: '#e0f1f0',
  warning: '#b7791f',
  warningSoft: '#fbf1e0',
  error: '#c4383b',
  errorSoft: '#fbeaea',
  info: '#148283',
  infoSoft: '#e0f1f0',
} as const

/** Role tokens: what components actually reference. */
export const roles = {
  surfacePrimary: neutral[0],
  surfaceSecondary: neutral[50],
  surfaceTertiary: neutral[100],
  surfaceBrand: teal[50],
  surfaceBrandStrong: teal[700],
  textPrimary: neutral[800],
  textSecondary: neutral[600],
  textMuted: neutral[500],
  textOnBrand: neutral[0],
  textBrand: teal[700],
  borderSubtle: neutral[200],
  borderStrong: neutral[300],
  borderBrand: teal[300],
  focusRing: teal[400],
} as const

/**
 * Accent families. aqua, mint and blue are teal tints, indigo is the neutral white/grey family,
 * coral is the functional alert family (unread badges). Owner-approved palette: page #E9EEF2,
 * teal #148283, white #FFFFFF, soft teal #E0F1F0.
 */
export const accent = {
  aqua: { 50: '#e0f1f0', 100: '#d1e2e5', 200: '#b1d3d7', 300: '#85c3c3', 500: '#3e9c9e', 700: '#148283' },
  blue: { 50: '#d1e2e5', 100: '#b1d3d7', 500: '#3e9c9e', 700: '#0f6872' },
  indigo: { 50: '#ffffff', 100: '#e9eef2', 500: '#575859', 700: '#363433' },
  coral: { 50: '#fbeaea', 100: '#f6d4d4', 500: '#d64541', 700: '#a8322f' },
  mint: { 50: '#e0f1f0', 100: '#d1e2e5', 500: '#3e9c9e', 700: '#148283' },
} as const
