import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiActionButton } from './ApiActionButton'
import { initI18n } from '../i18n'

initI18n()

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('ApiActionButton', () => {
  it('disables itself, shows a spinner while pending, then restores', async () => {
    const d = deferred<string>()
    const action = vi.fn(() => d.promise)
    const onSuccess = vi.fn()
    render(
      <ApiActionButton action={action} onSuccess={onSuccess}>
        Save
      </ApiActionButton>,
    )

    const button = screen.getByRole('button', { name: /save/i })
    expect(button).toBeEnabled()
    expect(screen.queryByRole('status')).toBeNull()

    await userEvent.click(button)
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('status')).toBeInTheDocument()

    d.resolve('done')
    await waitFor(() => expect(button).toBeEnabled())
    expect(screen.queryByRole('status')).toBeNull()
    expect(onSuccess).toHaveBeenCalledWith('done')
    expect(action).toHaveBeenCalledTimes(1)
  })

  it('ignores duplicate clicks while pending', async () => {
    const d = deferred<void>()
    const action = vi.fn(() => d.promise)
    render(<ApiActionButton action={action}>Send</ApiActionButton>)
    const button = screen.getByRole('button')

    await userEvent.click(button)
    await userEvent.click(button) // disabled: no-op
    await userEvent.click(button)
    expect(action).toHaveBeenCalledTimes(1)
    d.resolve()
    await waitFor(() => expect(button).toBeEnabled())
  })

  it('reports errors and restores the button', async () => {
    const action = vi.fn(() => Promise.reject(new Error('boom')))
    const onError = vi.fn()
    render(
      <ApiActionButton action={action} onError={onError}>
        Try
      </ApiActionButton>,
    )
    await userEvent.click(screen.getByRole('button'))
    await waitFor(() => expect(onError).toHaveBeenCalledTimes(1))
    const reported = onError.mock.calls[0]![0] as Error
    expect(reported.message).toBe('boom')
    expect(screen.getByRole('button')).toBeEnabled()
  })
})
