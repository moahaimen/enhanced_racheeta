import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as providersApi from '../../api/endpoints/providers'
import * as referenceApi from '../../api/endpoints/reference'
import { tokenStore } from '../../api/tokens'
import { baghdad, basra, cardiology, dentistry, makeCard } from '../../test/providerFixtures'
import { deferred, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/providers')
vi.mock('../../api/endpoints/reference')

function page(results = [makeCard()], count = results.length, next: string | null = null, previous: string | null = null) {
  return { count, next, previous, results }
}

describe('ProvidersPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    tokenStore.clear()
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([baghdad, basra])
    vi.mocked(referenceApi.listSpecialties).mockResolvedValue([cardiology, dentistry])
    vi.mocked(referenceApi.listCities).mockResolvedValue([
      { id: 'c-1', governorate: baghdad.id, slug: 'baghdad', name_ar: 'بغداد', name_en: 'Baghdad' },
    ])
  })

  it('shows loading, then provider cards from the API', async () => {
    const pending = deferred<ReturnType<typeof page>>()
    vi.mocked(providersApi.listProviders).mockReturnValue(pending.promise)
    renderApp('/providers')
    expect(screen.getAllByTestId('async-loading').length).toBeGreaterThan(0)
    pending.resolve(page([makeCard({ display_name: 'Dr Alpha' }), makeCard({ id: 'p-2', display_name: 'Dr Beta' })]))
    expect(await screen.findByText('Dr Alpha')).toBeInTheDocument()
    expect(screen.getByText('Dr Beta')).toBeInTheDocument()
    expect(screen.getByTestId('results-count')).toHaveTextContent('2')
    expect(screen.getAllByText('أمراض القلب').length).toBeGreaterThan(0) // Arabic specialty name
    expect(screen.getByRole('link', { name: 'Dr Alpha' })).toHaveAttribute('href', '/providers/p-1')
  })

  it('shows the empty state', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue(page([], 0))
    renderApp('/providers')
    expect(await screen.findByTestId('providers-empty')).toBeInTheDocument()
  })

  it('shows the error state with retry', async () => {
    vi.mocked(providersApi.listProviders)
      .mockRejectedValueOnce(new ApiError(0, 'network_error', 'offline'))
      .mockResolvedValueOnce(page())
    renderApp('/providers')
    const error = await screen.findByTestId('async-error')
    expect(error).toHaveTextContent('offline')
    await userEvent.click(within(error).getByRole('button'))
    expect(await screen.findByText('Dr Example')).toBeInTheDocument()
  })

  it('passes filters to the API and writes them to the URL', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue(page())
    const { router } = renderApp('/providers')
    await screen.findByText('Dr Example')
    const filters = screen.getByRole('form', { name: /التصفية|filters/i })
    const [typeSelect, specialtySelect, governorateSelect] = within(filters).getAllByRole('combobox')
    await userEvent.selectOptions(typeSelect!, 'HOSPITAL')
    await userEvent.selectOptions(specialtySelect!, 'dentistry')
    await userEvent.selectOptions(governorateSelect!, basra.id)
    await waitFor(() =>
      expect(vi.mocked(providersApi.listProviders).mock.calls.at(-1)![0]).toMatchObject({
        type: 'HOSPITAL',
        specialty: 'dentistry',
        governorate: basra.id,
        page: 1,
      }),
    )
    expect(router.state.location.search).toContain('type=HOSPITAL')
    expect(router.state.location.search).toContain('governorate=g-basra')
  })

  it('loads cities for the chosen governorate and resets the city on change', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue(page())
    renderApp('/providers?governorate=g-baghdad&city=c-1')
    await screen.findByText('Dr Example')
    await waitFor(() => expect(referenceApi.listCities).toHaveBeenCalledWith('g-baghdad', expect.anything()))
    const filters = screen.getByRole('form', { name: /التصفية|filters/i })
    const governorateSelect = within(filters).getAllByRole('combobox')[2]!
    await userEvent.selectOptions(governorateSelect, basra.id)
    await waitFor(() =>
      expect(vi.mocked(providersApi.listProviders).mock.calls.at(-1)![0]).toMatchObject({
        governorate: basra.id,
        city: '',
      }),
    )
  })

  it('paginates', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue(page([makeCard()], 30, 'next-url', null))
    const { router } = renderApp('/providers')
    await screen.findByText('Dr Example')
    await userEvent.click(screen.getByRole('button', { name: /التالي|next/i }))
    await waitFor(() => expect(router.state.location.search).toContain('page=2'))
    await waitFor(() =>
      expect(vi.mocked(providersApi.listProviders).mock.calls.at(-1)![0]).toMatchObject({ page: 2 }),
    )
  })
})
