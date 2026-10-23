import { useId } from 'react'

/**
 * Project-owned flat backdrop for the hero (inline SVG, no external assets): soft orb, hospital
 * towers, palms and leaves in the Racheeta palette. The practitioner photograph is layered over it
 * as a separate optimised image (`HeroVisual`); this file contains no text and no people.
 */
function Palm({ x, y, scale = 1, lean = 0 }: { x: number; y: number; scale?: number; lean?: number }) {
  const fronds = [-70, -38, -8, 22, 52, 82]
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <path d={`M0 0c${4 + lean} -34 ${8 + lean * 2} -70 ${lean * 3} -104`} stroke="#6b8f5e" strokeWidth="5" fill="none" strokeLinecap="round" />
      <g transform={`translate(${lean * 3} -104)`} fill="#2f9a63">
        {fronds.map((deg) => (
          <ellipse key={deg} cx="0" cy="-18" rx="6" ry="30" transform={`rotate(${deg})`} opacity=".9" />
        ))}
      </g>
    </g>
  )
}

export function HeroBackdrop({ className }: { className?: string }) {
  const id = useId()
  return (
    <svg className={className} viewBox="0 0 520 470" aria-hidden="true" focusable="false" preserveAspectRatio="xMidYMax meet">
      <defs>
        <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#bfe9ee" />
          <stop offset="1" stopColor="#eaf8f6" />
        </linearGradient>
        <linearGradient id={`${id}-tower`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#9fd2ef" />
          <stop offset="1" stopColor="#4f9fd2" />
        </linearGradient>
        <linearGradient id={`${id}-ground`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#d9f1ee" stopOpacity="0" />
          <stop offset=".18" stopColor="#d9f1ee" />
          <stop offset=".82" stopColor="#d9f1ee" />
          <stop offset="1" stopColor="#d9f1ee" stopOpacity="0" />
        </linearGradient>
        <linearGradient id={`${id}-orb`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7fd3c7" stopOpacity=".9" />
          <stop offset="1" stopColor="#35a8c4" stopOpacity=".75" />
        </linearGradient>
      </defs>
      <circle cx="270" cy="236" r="222" fill={`url(#${id}-orb)`} opacity=".3" />
      <circle cx="270" cy="236" r="176" fill={`url(#${id}-sky)`} />
      <g>
        <rect x="318" y="84" width="104" height="250" rx="12" fill={`url(#${id}-tower)`} />
        {Array.from({ length: 9 }, (_, r) =>
          Array.from({ length: 5 }, (_, c) => <rect key={`${r}${c}`} x={330 + c * 18.5} y={102 + r * 24} width="10" height="13" rx="2.5" fill="#fff" opacity=".8" />),
        )}
        <rect x="414" y="152" width="78" height="182" rx="12" fill="#6db2dd" />
        {Array.from({ length: 6 }, (_, r) =>
          Array.from({ length: 4 }, (_, c) => <rect key={`b${r}${c}`} x={424 + c * 17.5} y={168 + r * 24} width="9" height="13" rx="2.5" fill="#fff" opacity=".75" />),
        )}
        <rect x="378" y="44" width="38" height="38" rx="10" fill="#fff" />
        <path d="M397 52v22M386 63h22" stroke="#e5624b" strokeWidth="6" strokeLinecap="round" />
      </g>
      <Palm x={300} y={346} scale={0.95} lean={-3} />
      <Palm x={456} y={350} scale={1} lean={3} />
      <g fill="#2fa86a" opacity=".85">
        <path d="M40 392c8-58 48-92 92-100-8 38-38 80-92 100z" />
        <path d="M18 404c-4-44 20-80 56-100-2 34-18 70-56 100z" opacity=".7" />
      </g>
      <path d="M0 436c110-22 210-14 300-4s170 12 220-8v46H0z" fill={`url(#${id}-ground)`} />
    </svg>
  )
}
