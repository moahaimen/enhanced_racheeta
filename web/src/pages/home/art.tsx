import { useId } from 'react'

/**
 * Project-owned flat illustrations (inline SVG, a few KB each, no external assets or licensing
 * questions). Decorative only: every svg is aria-hidden and carries no text.
 */
type SceneProps = { className?: string }

const SKIN = '#e9b996'
const COAT = '#ffffff'
const TEAL = '#15857e'
const DEEP = '#0d4f4a'

function Window({ x, y, w = 9, h = 11, fill = '#ffffff', o = 0.75 }: { x: number; y: number; w?: number; h?: number; fill?: string; o?: number }) {
  return <rect x={x} y={y} width={w} height={h} rx={2} fill={fill} opacity={o} />
}

function windows(x0: number, y0: number, cols: number, rows: number, dx = 16, dy = 18, o = 0.75) {
  const out = []
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) out.push(<Window key={`${r}-${c}`} x={x0 + c * dx} y={y0 + r * dy} o={o} />)
  return out
}

function Doctor({ x = 0, y = 0, scale = 1, tone = TEAL }: { x?: number; y?: number; scale?: number; tone?: string }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <path d="M-86 170c0-40 30-62 86-62s86 22 86 62v10H-86z" fill={COAT} />
      <path d="M-24 108l24 46 24-46c-8-3-16-4-24-4s-16 1-24 4z" fill={tone} />
      <path d="M-24 108l24 46M24 108l-24 46" stroke="#cfe8e5" strokeWidth="2.5" fill="none" />
      <rect x="-12" y="84" width="24" height="26" rx="10" fill={SKIN} />
      <ellipse cx="0" cy="52" rx="40" ry="44" fill="#2b2a33" />
      <circle cx="0" cy="60" r="35" fill={SKIN} />
      <path d="M-38 52c4-34 70-34 76 0-12-14-30-20-38-20s-26 6-38 20z" fill="#2b2a33" />
      <circle cx="-12" cy="62" r="3" fill="#3a2a22" />
      <circle cx="12" cy="62" r="3" fill="#3a2a22" />
      <path d="M-9 76c6 6 12 6 18 0" stroke="#a45f4a" strokeWidth="3" fill="none" strokeLinecap="round" />
      <circle cx="-22" cy="72" r="5" fill="#f08c7a" opacity=".35" />
      <circle cx="22" cy="72" r="5" fill="#f08c7a" opacity=".35" />
      <path d="M-46 112c0 36 12 50 30 54" stroke={DEEP} strokeWidth="5" fill="none" strokeLinecap="round" />
      <path d="M46 112c0 36-12 50-30 54" stroke={DEEP} strokeWidth="5" fill="none" strokeLinecap="round" />
      <circle cx="-14" cy="168" r="8" fill="#9ed8d3" stroke={DEEP} strokeWidth="4" />
    </g>
  )
}

export function HeroArt({ className }: SceneProps) {
  const id = useId()
  return (
    <svg className={className} viewBox="0 0 520 470" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#bfe9ee" />
          <stop offset="1" stopColor="#e9f8f6" />
        </linearGradient>
        <linearGradient id={`${id}-tower`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#8cc9ec" />
          <stop offset="1" stopColor="#4c9fd1" />
        </linearGradient>
        <linearGradient id={`${id}-orb`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7fd3c7" stopOpacity=".9" />
          <stop offset="1" stopColor="#35a8c4" stopOpacity=".75" />
        </linearGradient>
      </defs>
      <circle cx="285" cy="235" r="215" fill={`url(#${id}-orb)`} opacity=".35" />
      <circle cx="285" cy="235" r="165" fill={`url(#${id}-sky)`} />
      <g>
        <rect x="318" y="96" width="92" height="212" rx="10" fill={`url(#${id}-tower)`} />
        {windows(328, 114, 5, 8, 16.5, 22, 0.8)}
        <rect x="404" y="150" width="70" height="158" rx="10" fill="#6db2dd" />
        {windows(412, 164, 4, 6, 16, 22, 0.75)}
        <rect x="384" y="60" width="34" height="34" rx="9" fill="#ffffff" />
        <path d="M401 68v18M392 77h18" stroke="#e5624b" strokeWidth="5" strokeLinecap="round" />
      </g>
      <g fill="#2fa86a" opacity=".85">
        <path d="M70 380c10-60 52-96 96-102-10 38-40 82-96 102z" />
        <path d="M44 392c-4-46 20-84 58-104-2 36-18 74-58 104z" opacity=".7" />
        <path d="M120 400c18-44 58-70 98-72-14 34-46 60-98 72z" opacity=".55" />
      </g>
      <path d="M0 430c110-22 210-14 300-4s170 12 220-8v52H0z" fill="#d9f1ee" />
      <Doctor x={226} y={238} scale={1.45} />
      <g transform="rotate(-8 370 380)">
        <rect x="328" y="338" width="108" height="140" rx="14" fill="#2a3b3a" />
        <rect x="336" y="346" width="92" height="124" rx="8" fill="#e8f5f6" />
        <rect x="346" y="358" width="72" height="9" rx="4" fill="#15857e" opacity=".85" />
        <rect x="346" y="376" width="56" height="7" rx="3.5" fill="#9bb7ba" />
        <rect x="346" y="390" width="64" height="7" rx="3.5" fill="#9bb7ba" />
        <path d="M346 430l14-16 12 10 14-24 14 18" stroke="#15857e" strokeWidth="3.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  )
}

function Bg({ id, from, to }: { id: string; from: string; to: string }) {
  return (
    <>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={from} />
          <stop offset="1" stopColor={to} />
        </linearGradient>
      </defs>
      <rect width="320" height="170" fill={`url(#${id})`} />
    </>
  )
}

const frame = { viewBox: '0 0 320 170', preserveAspectRatio: 'xMidYMid slice', 'aria-hidden': true, focusable: 'false' } as const

export function SceneDoctors({ className }: SceneProps) {
  const id = useId()
  return (
    <svg className={className} {...frame}>
      <Bg id={id} from="#d8f1f3" to="#eaf8f5" />
      <circle cx="248" cy="40" r="70" fill="#ffffff" opacity=".5" />
      <g transform="translate(86 6)">
        <rect x="150" y="30" width="86" height="100" rx="12" fill="#fff" />
        <rect x="150" y="30" width="86" height="24" rx="12" fill="#15857e" />
        {[0, 1, 2, 3].map((r) => [0, 1, 2, 3].map((c) => <circle key={`${r}${c}`} cx={166 + c * 18} cy={72 + r * 14} r="3.4" fill={r === 1 && c === 2 ? '#e5624b' : '#cfe3e5'} />))}
      </g>
      <Doctor x={92} y={34} scale={0.9} />
    </svg>
  )
}

export function SceneHospitals({ className }: SceneProps) {
  const id = useId()
  return (
    <svg className={className} {...frame}>
      <Bg id={id} from="#cfe6fa" to="#eaf4fd" />
      <rect x="40" y="62" width="62" height="108" rx="6" fill="#8dbde6" />
      {windows(48, 74, 4, 5, 14, 18, 0.8)}
      <rect x="110" y="30" width="104" height="140" rx="8" fill="#4f9bd3" />
      {windows(122, 44, 6, 6, 15, 20, 0.85)}
      <rect x="150" y="136" width="24" height="34" rx="4" fill="#ffffff" opacity=".9" />
      <rect x="150" y="10" width="24" height="24" rx="7" fill="#fff" />
      <path d="M162 15v14M155 22h14" stroke="#e5624b" strokeWidth="4" strokeLinecap="round" />
      <rect x="222" y="74" width="56" height="96" rx="6" fill="#74afdc" />
      {windows(230, 86, 3, 4, 15, 20, 0.8)}
      <path d="M0 160c80-10 160 6 320-6v16H0z" fill="#2fa86a" opacity=".55" />
    </svg>
  )
}

export function SceneProducts({ className }: SceneProps) {
  const id = useId()
  return (
    <svg className={className} {...frame}>
      <Bg id={id} from="#dbeafd" to="#eef5fe" />
      <g transform="rotate(-28 110 90)">
        <rect x="60" y="64" width="110" height="38" rx="19" fill="#3b82d6" />
        <rect x="115" y="64" width="55" height="38" rx="19" fill="#ffffff" />
        <rect x="115" y="64" width="20" height="38" fill="#ffffff" />
      </g>
      <g transform="rotate(24 220 70)">
        <rect x="180" y="48" width="96" height="34" rx="17" fill="#ffffff" stroke="#c9dcf5" strokeWidth="2" />
        <rect x="180" y="48" width="48" height="34" rx="17" fill="#e5624b" />
        <rect x="210" y="48" width="18" height="34" fill="#e5624b" />
      </g>
      <rect x="200" y="100" width="64" height="52" rx="8" fill="#ffffff" stroke="#c9dcf5" strokeWidth="2" />
      <path d="M232 112v28M218 126h28" stroke="#15857e" strokeWidth="6" strokeLinecap="round" />
      <rect x="36" y="112" width="40" height="46" rx="8" fill="#15857e" />
      <rect x="44" y="102" width="24" height="14" rx="4" fill="#0d4f4a" />
      <rect x="44" y="126" width="24" height="16" rx="3" fill="#ffffff" opacity=".85" />
    </svg>
  )
}

export function SceneJobs({ className }: SceneProps) {
  const id = useId()
  return (
    <svg className={className} {...frame}>
      <Bg id={id} from="#e3e1fb" to="#f1f0fd" />
      <rect x="64" y="58" width="112" height="84" rx="14" fill="#6a5ae0" />
      <rect x="100" y="42" width="40" height="22" rx="8" fill="none" stroke="#4b3fb0" strokeWidth="7" />
      <rect x="64" y="92" width="112" height="8" fill="#4b3fb0" opacity=".5" />
      <rect x="112" y="86" width="16" height="20" rx="4" fill="#fff" />
      <rect x="170" y="70" width="100" height="70" rx="12" fill="#fff" stroke="#d6d2f6" strokeWidth="2" />
      <circle cx="198" cy="96" r="12" fill="#e9b996" />
      <rect x="216" y="88" width="42" height="7" rx="3.5" fill="#cfcaf3" />
      <rect x="216" y="102" width="30" height="7" rx="3.5" fill="#e1defa" />
      <path d="M184 124l8 8 14-16" stroke="#2fa86a" strokeWidth="5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="214" y="122" width="44" height="7" rx="3.5" fill="#e1defa" />
    </svg>
  )
}

export function SceneEstate({ className }: SceneProps) {
  const id = useId()
  return (
    <svg className={className} {...frame}>
      <Bg id={id} from="#ffe6df" to="#fff3ef" />
      <rect x="86" y="52" width="150" height="108" rx="8" fill="#fff" stroke="#f3cfc6" strokeWidth="2" />
      <path d="M72 58l89-38 89 38z" fill="#e5624b" />
      {windows(102, 74, 4, 2, 32, 30, 1)}
      <rect x="146" y="116" width="30" height="44" rx="5" fill="#15857e" />
      <circle cx="170" cy="140" r="2.6" fill="#fff" />
      <g transform="translate(248 96)">
        <circle cx="14" cy="14" r="12" fill="none" stroke="#f0a090" strokeWidth="6" />
        <path d="M24 22l30 30M42 40l8-8M50 48l8-8" stroke="#f0a090" strokeWidth="6" strokeLinecap="round" />
      </g>
      <rect x="28" y="108" width="6" height="52" rx="3" fill="#b8856f" />
      <rect x="14" y="98" width="34" height="22" rx="5" fill="#fff" stroke="#f3cfc6" strokeWidth="2" />
    </svg>
  )
}

export function SceneCompanies({ className }: SceneProps) {
  const id = useId()
  return (
    <svg className={className} {...frame}>
      <Bg id={id} from="#d3f1e1" to="#e9f8ef" />
      <path d="M96 40h28v38l34 62a10 10 0 0 1-9 15H71a10 10 0 0 1-9-15l34-62z" fill="#fff" stroke="#a6dcc0" strokeWidth="3" />
      <path d="M78 118h66l14 26a8 8 0 0 1-7 12H71a8 8 0 0 1-7-12z" fill="#2fa86a" opacity=".85" />
      <circle cx="104" cy="104" r="5" fill="#fff" opacity=".9" />
      <circle cx="118" cy="92" r="3.4" fill="#fff" opacity=".9" />
      <rect x="190" y="68" width="92" height="82" rx="10" fill="#fff" stroke="#a6dcc0" strokeWidth="3" />
      <rect x="204" y="84" width="22" height="22" rx="5" fill="#15857e" />
      <rect x="234" y="84" width="34" height="8" rx="4" fill="#a6dcc0" />
      <rect x="234" y="98" width="24" height="8" rx="4" fill="#cfeedd" />
      <path d="M204 126h64M204 138h44" stroke="#cfeedd" strokeWidth="7" strokeLinecap="round" />
    </svg>
  )
}
