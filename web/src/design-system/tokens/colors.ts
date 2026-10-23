/**
 * Racheeta colour tokens. Source of truth for the values; `tokens.css`
 * exposes the same values as CSS custom properties (a test keeps them equal).
 */
export const teal = {
  50: '#eef8f7',
  100: '#d5efec',
  200: '#abdfd9',
  300: '#7ccac2',
  400: '#4db1a8',
  500: '#2a9a90',
  600: '#1f7f77',
  700: '#196660',
  800: '#154f4b',
  900: '#103c39',
} as const

export const neutral = {
  0: '#ffffff',
  50: '#f7f9f9',
  100: '#eef1f2',
  200: '#e2e7e9',
  300: '#cbd3d6',
  400: '#9aa6ab',
  500: '#6b7a80',
  600: '#4a575c',
  700: '#34403f',
  800: '#22302f',
  900: '#15201f',
} as const

export const semantic = {
  success: '#1e8e5a',
  successSoft: '#e8f6ef',
  warning: '#b7791f',
  warningSoft: '#fbf3e4',
  error: '#c4383b',
  errorSoft: '#fbeaea',
  info: '#2f6fb7',
  infoSoft: '#e9f1fb',
} as const

/** Role tokens: what components actually reference. */
export const roles = {
  surfacePrimary: neutral[0],
  surfaceSecondary: neutral[50],
  surfaceTertiary: neutral[100],
  surfaceBrand: teal[50],
  surfaceBrandStrong: teal[600],
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

/** Public-site accents: one family per product area, all derived from the Racheeta teal. */
export const accent = {
  aqua: { 50: '#effafb', 100: '#d9f3f6', 200: '#b3e6ec', 300: '#7fd3de', 500: '#1fa3b8', 700: '#0f6f80' },
  blue: { 50: '#eef4fd', 100: '#dbe8fb', 500: '#3b82d6', 700: '#2a5fae' },
  indigo: { 50: '#f1f0fd', 100: '#e1defa', 500: '#6a5ae0', 700: '#4b3fb0' },
  coral: { 50: '#fff1ee', 100: '#ffddd6', 500: '#e5624b', 700: '#b83f2a' },
  mint: { 50: '#edf9f2', 100: '#d3f1e1', 500: '#2fa86a', 700: '#1b7a4b' },
} as const
