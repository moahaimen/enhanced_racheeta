import type { SVGProps } from 'react'

import { paths, type IconName } from './paths'

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'name'> {
  name: IconName
  size?: number
  /** Accessible label; without it the icon is decorative (aria-hidden). */
  label?: string
  /** Mirror in RTL (for directional icons such as arrows/chevrons). */
  flipInRtl?: boolean
}

/**
 * Racheeta line icons: one 24px grid, 1.75px stroke, `currentColor`.
 * Directional icons pass `flipInRtl` so they follow the reading direction.
 */
export function Icon({ name, size = 20, label, flipInRtl = false, className = '', ...rest }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
      className={`${flipInRtl ? 'rtl-flip' : ''} ${className}`.trim()}
      data-icon={name}
      {...rest}
    >
      {paths[name]}
    </svg>
  )
}
