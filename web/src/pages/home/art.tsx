import { useId } from 'react'

/**
 * Project-owned flat backdrop for the hero (inline SVG, no external assets): warm mint disc,
 * peach sun, sage leaves. The practitioner photograph is layered over it as a separate optimised
 * image (`HeroVisual`); this file contains no text and no people.
 */
export function HeroBackdrop({ className }: { className?: string }) {
  const id = useId()
  return (
    <svg className={className} viewBox="0 0 520 470" aria-hidden="true" focusable="false" preserveAspectRatio="xMidYMax meet">
      <defs>
        <linearGradient id={`${id}-disc`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#d1e2e5" />
        </linearGradient>
        <linearGradient id={`${id}-ground`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#dddfe4" stopOpacity="0" />
          <stop offset=".2" stopColor="#dddfe4" />
          <stop offset=".8" stopColor="#dddfe4" />
          <stop offset="1" stopColor="#dddfe4" stopOpacity="0" />
        </linearGradient>
      </defs>
      <circle cx="262" cy="236" r="214" fill="#e0f1f0" opacity=".55" />
      <circle cx="262" cy="236" r="178" fill={`url(#${id}-disc)`} />
      <circle cx="404" cy="108" r="62" fill="#b1d3d7" opacity=".55" />
      <rect x="430" y="196" width="58" height="58" rx="16" fill="#fff" opacity=".9" />
      <path d="M459 210v30M444 225h30" stroke="#148283" strokeWidth="7" strokeLinecap="round" />
      <g fill="#85c3c3">
        <path d="M44 410c8-58 48-92 92-100-8 38-38 80-92 100z" opacity=".85" />
        <path d="M18 420c-4-44 20-80 56-100-2 34-18 70-56 100z" opacity=".55" />
        <path d="M486 300c-30 6-52 30-60 62 28-8 52-30 60-62z" opacity=".7" />
      </g>
      <path d="M0 438c110-18 210-12 300-3s170 10 220-6v41H0z" fill={`url(#${id}-ground)`} />
    </svg>
  )
}
