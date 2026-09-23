import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { initI18n } from '../../../i18n'
import { Button, IconButton } from './Button'

initI18n()

describe('Button', () => {
  it('is a real button with type=button by default', () => {
    render(<Button>Save</Button>)
    const button = screen.getByRole('button', { name: 'Save' })
    expect(button).toHaveAttribute('type', 'button')
    expect(button).toBeEnabled()
  })

  it('while loading: disabled, busy, spinner shown, label kept for layout', async () => {
    const onClick = vi.fn()
    render(
      <Button loading loadingLabel="Saving…" onClick={onClick}>
        Save
      </Button>,
    )
    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(button).toHaveTextContent('Saving…')
    await userEvent.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('IconButton always has an accessible name', () => {
    render(<IconButton label="Open menu">x</IconButton>)
    expect(screen.getByRole('button', { name: 'Open menu' })).toBeInTheDocument()
  })
})
