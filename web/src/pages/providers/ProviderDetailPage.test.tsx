import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as providersApi from '../../api/endpoints/providers'
import { tokenStore } from '../../api/tokens'
import { makePublic } from '../../test/providerFixtures'
import { deferred, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/providers')
vi.mock('../../api/endpoints/reference')

describe('ProviderDetailPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
  })

  it('shows loading then only real API data', async () => {
    const pending = deferred<ReturnType<typeof makePublic>>()
    vi.mocked(providersApi.getProvider).mockReturnValue(pending.promise)
    renderApp('/providers/p-1')
    expect(screen.getByTestId('async-loading')).toBeInTheDocument()
    pending.resolve(makePublic())
    expect(await screen.findByRole('heading', { name: 'Dr Example' })).toBeInTheDocument()
    expect(providersApi.getProvider).toHaveBeenCalledWith('p-1', expect.anything())
    expect(screen.getByText('About text')).toBeInTheDocument()
    expect(screen.getByText('Consultation')).toBeInTheDocument()
    expect(screen.getByText('+9647700000000')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'City Hospital' })).toHaveAttribute('href', '/providers/p-h')
    expect(screen.queryByText(/rating|تقييم/i)).toBeNull()
  })

  it('shows the empty services message', async () => {
    vi.mocked(providersApi.getProvider).mockResolvedValue(makePublic({ services: [], related_providers: [] }))
    renderApp('/providers/p-1')
    expect(await screen.findByText(/لم يُدرج مقدّم الخدمة خدمات|has not listed services/i)).toBeInTheDocument()
  })

  it('shows a not-found message for 404', async () => {
    vi.mocked(providersApi.getProvider).mockRejectedValue(new ApiError(404, 'not_found', 'nope'))
    renderApp('/providers/missing')
    const error = await screen.findByTestId('async-error')
    expect(error).toHaveTextContent(/غير موجود|does not exist/i)
  })
})
