import { useEffect, useState, type ReactNode } from 'react'

import { Icon } from '../design-system'
import dir from './directory.module.css'

/** Same breakpoint as the directory filter sidebar (directory.module.css). */
const DESKTOP = '(min-width: 960px)'

const canMatch = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function'

function useIsDesktop(): boolean {
  // Without matchMedia (tests, very old browsers) the filters stay expanded, as before.
  const [desktop, setDesktop] = useState(() => (canMatch() ? window.matchMedia(DESKTOP).matches : true))
  useEffect(() => {
    if (!canMatch()) return
    const query = window.matchMedia(DESKTOP)
    const onChange = (event: MediaQueryListEvent) => setDesktop(event.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])
  return desktop
}

/**
 * Directory filter fields: always visible in the desktop sidebar; on narrower screens a disclosure
 * (closed by default) so the results start on the first screen. The search field stays outside it.
 */
export function FilterDisclosure({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  const desktop = useIsDesktop()
  if (desktop) return <div className={className}>{children}</div>
  return (
    <details className={dir.disclosure}>
      <summary>
        <Icon name="filter" size={18} />
        <span>{label}</span>
        <Icon name="chevronDown" size={18} className={dir.disclosureChevron} />
      </summary>
      <div className={className}>{children}</div>
    </details>
  )
}
