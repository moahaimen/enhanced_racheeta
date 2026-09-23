import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiRequest } from './client'
import { tokenStore } from './tokens'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('apiRequest', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    fetchMock.mockReset()
    tokenStore.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends JSON and attaches the bearer token', async () => {
    tokenStore.set({ access: 'acc', refresh: 'ref' })
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { id: '1' }))

    const result = await apiRequest<{ id: string }>('/api/v1/me', { method: 'PATCH', body: { full_name: 'X' } })

    expect(result).toEqual({ id: '1' })
    const [url, init] = fetchMock.mock.calls[0]!
    const headers = init!.headers as Record<string, string>
    expect(url).toBe('/api/v1/me')
    expect(init!.method).toBe('PATCH')
    expect(headers.Authorization).toBe('Bearer acc')
    expect(init!.body).toBe(JSON.stringify({ full_name: 'X' }))
  })

  it('turns the error envelope into an ApiError', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(400, {
        error: { code: 'validation_error', message: 'Validation failed.', details: { email: ['Taken.'] } },
      }),
    )
    const error = await apiRequest('/api/v1/auth/register', { method: 'POST', body: {}, auth: false }).catch(
      (e: unknown) => e,
    )
    expect(error).toBeInstanceOf(ApiError)
    const apiError = error as ApiError
    expect(apiError.status).toBe(400)
    expect(apiError.code).toBe('validation_error')
    expect(apiError.fieldError('email')).toBe('Taken.')
  })

  it('refreshes once on 401 and retries with the new access token', async () => {
    tokenStore.set({ access: 'stale', refresh: 'ref-1' })
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: 'token_not_valid', message: 'expired' } }))
      .mockResolvedValueOnce(jsonResponse(200, { access: 'fresh', refresh: 'ref-2' }))
      .mockResolvedValueOnce(jsonResponse(200, { id: 'me' }))

    const result = await apiRequest<{ id: string }>('/api/v1/me')

    expect(result).toEqual({ id: 'me' })
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock.mock.calls[1]![0]).toBe('/api/v1/auth/refresh')
    const retryHeaders = fetchMock.mock.calls[2]![1]!.headers as Record<string, string>
    expect(retryHeaders.Authorization).toBe('Bearer fresh')
    expect(tokenStore.getRefresh()).toBe('ref-2')
  })

  it('clears the session when refresh fails', async () => {
    tokenStore.set({ access: 'stale', refresh: 'ref-1' })
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: 'token_not_valid', message: 'expired' } }))
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: 'token_not_valid', message: 'blacklisted' } }))

    await expect(apiRequest('/api/v1/me')).rejects.toBeInstanceOf(ApiError)
    expect(tokenStore.isAuthenticated()).toBe(false)
  })

  it('maps network failures to a network_error', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    const error = await apiRequest('/health/', { auth: false }).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).code).toBe('network_error')
  })
})
