import { useRef, type KeyboardEvent, type ReactNode } from 'react'

import styles from './Tabs.module.css'

export interface TabItem {
  id: string
  label: ReactNode
  icon?: ReactNode
}

export interface TabsProps {
  /** Stable id prefix shared with `tabPanelProps`. */
  id: string
  tabs: TabItem[]
  value: string
  onChange: (id: string) => void
  'aria-label': string
}

/** Accessible tab list (roving focus, arrow keys, Home/End). Panels are rendered by the caller. */
export function Tabs({ id: baseId, tabs, value, onChange, 'aria-label': ariaLabel }: TabsProps) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = tabs.findIndex((t) => t.id === value)
    if (index < 0) return
    const dir = document.documentElement.dir === 'rtl' ? -1 : 1
    let next: number | null = null
    if (event.key === 'ArrowRight') next = (index + dir + tabs.length) % tabs.length
    if (event.key === 'ArrowLeft') next = (index - dir + tabs.length) % tabs.length
    if (event.key === 'Home') next = 0
    if (event.key === 'End') next = tabs.length - 1
    if (next === null) return
    event.preventDefault()
    const target = tabs[next]
    if (target) {
      onChange(target.id)
      refs.current[next]?.focus()
    }
  }

  return (
    <div role="tablist" aria-label={ariaLabel} className={styles.list} onKeyDown={onKeyDown}>
      {tabs.map((tab, i) => {
        const selected = tab.id === value
        return (
          <button
            key={tab.id}
            ref={(el) => {
              refs.current[i] = el
            }}
            type="button"
            role="tab"
            id={`${baseId}-tab-${tab.id}`}
            aria-selected={selected}
            aria-controls={`${baseId}-panel-${tab.id}`}
            tabIndex={selected ? 0 : -1}
            className={styles.tab}
            onClick={() => onChange(tab.id)}
          >
            {tab.icon}
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
