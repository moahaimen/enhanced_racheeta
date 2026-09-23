import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { AsyncPage } from './AsyncPage'
import { initI18n } from '../i18n'

initI18n()

describe('AsyncPage', () => {
  it('shows loading, then renders the data', async () => {
    const load = vi.fn(() => Promise.resolve({ status: 'ok' }))
    render(<AsyncPage load={load}>{(data) => <p>status: {data.status}</p>}</AsyncPage>)

    expect(screen.getByTestId('async-loading')).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(await screen.findByText('status: ok')).toBeInTheDocument()
    expect(screen.queryByTestId('async-loading')).toBeNull()
  })

  it('shows an error with retry, and retries', async () => {
    const load = vi
      .fn<() => Promise<{ status: string }>>()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ status: 'ok' })
    render(<AsyncPage load={load}>{(data) => <p>status: {data.status}</p>}</AsyncPage>)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('offline')

    await userEvent.click(screen.getByRole('button'))
    await waitFor(() => expect(screen.getByText('status: ok')).toBeInTheDocument())
    expect(load).toHaveBeenCalledTimes(2)
  })
})
