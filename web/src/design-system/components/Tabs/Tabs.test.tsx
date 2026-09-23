import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { Tabs } from './Tabs'
import { tabPanelProps } from './tabPanelProps'

const TABS = [
  { id: 'a', label: 'Alpha' },
  { id: 'b', label: 'Beta' },
  { id: 'c', label: 'Gamma' },
]

function Harness() {
  const [value, setValue] = useState('a')
  return (
    <>
      <Tabs id="t" tabs={TABS} value={value} onChange={setValue} aria-label="Sections" />
      <div {...tabPanelProps('t', value)}>panel {value}</div>
    </>
  )
}

describe('Tabs', () => {
  it('selects with click and keyboard, exposes ARIA relations', async () => {
    document.documentElement.dir = 'ltr'
    render(<Harness />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel')).toHaveTextContent('panel a')
    expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', tabs[0]!.id)

    await userEvent.click(tabs[1]!)
    expect(screen.getByRole('tabpanel')).toHaveTextContent('panel b')

    tabs[1]!.focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('tabpanel')).toHaveTextContent('panel c')
    expect(document.activeElement).toBe(tabs[2])
    await userEvent.keyboard('{Home}')
    expect(screen.getByRole('tabpanel')).toHaveTextContent('panel a')
  })

  it('mirrors arrow keys in RTL', async () => {
    document.documentElement.dir = 'rtl'
    render(<Harness />)
    const tabs = screen.getAllByRole('tab')
    tabs[0]!.focus()
    await userEvent.keyboard('{ArrowLeft}')
    expect(screen.getByRole('tabpanel')).toHaveTextContent('panel b')
    document.documentElement.dir = 'ltr'
  })
})
