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
