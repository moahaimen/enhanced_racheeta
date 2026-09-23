export const fontFamily = {
  sans: "'IBM Plex Sans Arabic', 'Noto Sans Arabic', 'Segoe UI', system-ui, -apple-system, sans-serif",
  mono: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
} as const

export const fontWeight = { regular: 400, medium: 500, semibold: 600, bold: 700 } as const

/** Type scale (rem / unitless line-height). Display and H1 shrink on mobile in CSS. */
export const typeScale = {
  display: { size: 2.5, line: 1.15, weight: 700 },
  h1: { size: 2, line: 1.2, weight: 700 },
  h2: { size: 1.5, line: 1.25, weight: 700 },
  h3: { size: 1.25, line: 1.3, weight: 600 },
  section: { size: 1.125, line: 1.35, weight: 600 },
  body: { size: 1, line: 1.6, weight: 400 },
  bodySm: { size: 0.9375, line: 1.55, weight: 400 },
  label: { size: 0.875, line: 1.4, weight: 600 },
  caption: { size: 0.8125, line: 1.4, weight: 400 },
  button: { size: 0.9375, line: 1.2, weight: 600 },
} as const
