import { useId } from 'react'

const SKIN = ['#f0c8a8', '#e3b08a', '#d19a74', '#f4d3b8']
const HAIR = ['#2b2a33', '#3a2a22', '#1f2430', '#5a3b2a']
const SCRUBS = ['#15857e', '#2a66b8', '#1fa3b8', '#4b3fb0']

function pick<T>(list: T[], seed: string, salt: number): T {
  let hash = salt
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0
  return list[hash % list.length]!
}

/**
 * Neutral, project-owned illustration used when a practitioner has not uploaded a photo. It is a
 * placeholder, not a likeness: variants are derived from the profile id so cards differ but stay stable.
 */
export function PersonPlaceholder({ seed, size = 96 }: { seed: string; size?: number }) {
  const id = useId()
  const skin = pick(SKIN, seed, 1)
  const hair = pick(HAIR, seed, 2)
  const scrubs = pick(SCRUBS, seed, 3)
  return (
    <svg width={size} height={size} viewBox="0 0 96 96" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={`${id}-bg`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#d9f3f6" />
          <stop offset="1" stopColor="#e8f7ef" />
        </linearGradient>
        <clipPath id={`${id}-clip`}>
          <circle cx="48" cy="48" r="48" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${id}-clip)`}>
        <rect width="96" height="96" fill={`url(#${id}-bg)`} />
        <path d="M8 100c0-22 16-34 40-34s40 12 40 34z" fill="#fff" />
        <path d="M36 68l12 20 12-20c-4-1-8-2-12-2s-8 1-12 2z" fill={scrubs} />
        <rect x="42" y="52" width="12" height="16" rx="6" fill={skin} />
        <ellipse cx="48" cy="38" rx="19" ry="21" fill={hair} />
        <circle cx="48" cy="42" r="16.5" fill={skin} />
        <path d="M31 38c2-17 32-17 34 0-6-7-14-10-17-10s-11 3-17 10z" fill={hair} />
        <circle cx="42.4" cy="43" r="1.6" fill="#3a2a22" />
        <circle cx="53.6" cy="43" r="1.6" fill="#3a2a22" />
        <path d="M43 50c3 3 7 3 10 0" stroke="#a45f4a" strokeWidth="1.8" fill="none" strokeLinecap="round" />
        <path d="M27 70c0 14 8 20 16 22M69 70c0 14-8 20-16 22" stroke="#0d4f4a" strokeWidth="2.4" fill="none" strokeLinecap="round" />
      </g>
    </svg>
  )
}
