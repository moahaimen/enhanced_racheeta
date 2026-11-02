import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as referenceApi from '../../api/endpoints/reference'
import * as workspacesApi from '../../api/endpoints/workspaces'
import { tokenStore } from '../../api/tokens'
import type { Order, StoreProduct } from '../../api'
import { cart } from '../../cart/cart'
import { makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/workspaces')
vi.mock('../../api/endpoints/reference')

const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results })
const product = (id: string, title: string, extra: Partial<StoreProduct> = {}): StoreProduct => ({
  id,
  title,
  description: '',
  brand: '',
  model_name: '',
  price: '10000.00',
  currency: 'IQD',
  image_url: `/demo/products/${id}.svg`,
  in_stock: true,
  low_stock: false,
  category: { id: 'c', slug: 'mobility', name_ar: 'وسائل الحركة', name_en: 'Mobility aids' },
  company: { id: 'm-1', name: 'Rehab store' },
  ...extra,
})

beforeEach(() => {
  vi.resetAllMocks()
  tokenStore.clear()
  cart.clear()
  vi.mocked(workspacesApi.listStoreCategories).mockResolvedValue([])
  vi.mocked(referenceApi.listGovernorates).mockResolvedValue([])
})

describe('store, header cart and order status', () => {
  it('every card shows a photo; the chosen quantity goes to the cart and the header badge counts it', async () => {
    vi.mocked(workspacesApi.listStoreProducts).mockResolvedValue(page([product('walker', 'Walker'), product('cane', 'Cane', { in_stock: false })]))
    renderApp('/store')
    const cards = await screen.findAllByTestId('store-card')
    expect(cards).toHaveLength(2)
    for (const card of cards) expect(card.querySelector('img')).toHaveAttribute('src', expect.stringMatching(/\/demo\/products\//))
    expect(within(cards[1]!).getByRole('button', { name: /غير متوفر|out of stock/i })).toBeDisabled()
    await userEvent.click(within(cards[0]!).getByRole('button', { name: /زيادة|increase/i }))
    await userEvent.click(within(cards[0]!).getByRole('button', { name: /أضف إلى السلة|add to cart/i }))
    const badge = await screen.findAllByTestId('cart-badge')
    expect(badge[0]).toHaveTextContent('2')
    expect(within(cards[0]!).getByText(/في سلتك: قطعتان|in your cart: 2/i)).toBeInTheDocument()
  })

  it('the cart re-checks each item: out of stock and no-longer-sold block checkout; recent orders show progress', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PATIENT' }))
    cart.add({ product: 'walker', title: 'Walker', price: '10000.00', currency: 'IQD', merchantId: 'm-1', merchantName: 'Rehab store' }, 1)
    cart.add({ product: 'gone', title: 'Old item', price: '5000.00', currency: 'IQD', merchantId: 'm-1', merchantName: 'Rehab store' }, 1)
    vi.mocked(workspacesApi.getStoreProduct).mockImplementation(async (id) => {
      if (id === 'gone') throw new ApiError(404, 'not_found', 'Not found.')
      return product('walker', 'Walker', { in_stock: false })
    })
    vi.mocked(workspacesApi.getDeliveryDefaults).mockResolvedValue({ governorate: null, city: null, address: '', phone: '' })
    vi.mocked(workspacesApi.listMyOrders).mockResolvedValue(
      page([{ id: 'o1', number: 'RCH-1', status: 'SHIPPED', total: '10000.00', currency: 'IQD', merchant: { id: 'm-1', name: 'Rehab store' } } as Order]),
    )
    renderApp('/cart')
    const lines = await screen.findAllByTestId('cart-line')
    await waitFor(() => expect(within(lines[0]!).getByText(/غير متوفر|out of stock/i)).toBeInTheDocument())
    expect(within(lines[1]!).getByText(/لم يعد متاحاً|no longer available/i)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /تأكيد الطلب|place order/i })).toBeDisabled()
    const tracker = await screen.findByTestId('order-tracker')
    expect(within(tracker).getByText(/تم الشحن|shipped/i).closest('li')).toHaveAttribute('aria-current', 'step')
  })

  it('checkout is pre-filled from the last order and the device location picks the governorate', async () => {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PATIENT' }))
    cart.add({ product: 'walker', title: 'Walker', price: '10000.00', currency: 'IQD', merchantId: 'm-1', merchantName: 'Rehab store' }, 1)
    vi.mocked(workspacesApi.getStoreProduct).mockResolvedValue(product('walker', 'Walker'))
    vi.mocked(workspacesApi.listMyOrders).mockResolvedValue(page([]))
    vi.mocked(workspacesApi.getDeliveryDefaults).mockResolvedValue({ governorate: 'g-bgd', city: null, address: 'Karrada, street 5', phone: '07701234567' })
    vi.mocked(referenceApi.listGovernorates).mockResolvedValue([
      { id: 'g-bgd', country: 'iq', slug: 'baghdad', name_ar: 'بغداد', name_en: 'Baghdad' },
      { id: 'g-bsr', country: 'iq', slug: 'basra', name_ar: 'البصرة', name_en: 'Basra' },
    ] as never)
    vi.mocked(workspacesApi.placeOrder).mockResolvedValue({ id: 'o', number: 'RCH-9' } as Order)
    const getCurrentPosition = vi.fn((ok: PositionCallback) => ok({ coords: { latitude: 30.5, longitude: 47.8 } } as GeolocationPosition))
    Object.defineProperty(navigator, 'geolocation', { value: { getCurrentPosition }, configurable: true })
    renderApp('/cart')
    const form = await screen.findByTestId('checkout-form')
    expect(within(form).getByLabelText(/عنوان التوصيل|delivery address/i)).toHaveValue('Karrada, street 5')
    expect(within(form).getByLabelText(/رقم التواصل|contact phone/i)).toHaveValue('07701234567')
    await userEvent.click(within(form).getByRole('button', { name: /استخدم موقعي الحالي|use my current location/i }))
    expect(within(form).getByLabelText(/المحافظة|governorate/i)).toHaveValue('g-bsr') // nearest to the shared position
    expect(within(form).getByTestId('delivery-pin')).toBeInTheDocument()
    await userEvent.click(within(form).getByRole('button', { name: /تأكيد الطلب|place order/i }))
    await waitFor(() => expect(workspacesApi.placeOrder).toHaveBeenCalledTimes(1))
    expect(vi.mocked(workspacesApi.placeOrder).mock.calls[0]![0]).toMatchObject({ governorate: 'g-bsr', latitude: '30.500000', longitude: '47.800000', phone: '07701234567' })
  })
})
