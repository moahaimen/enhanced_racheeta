import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as authApi from '../../api/endpoints/auth'
import * as commerceApi from '../../api/endpoints/commerce'
import * as referenceApi from '../../api/endpoints/reference'
import * as workspacesApi from '../../api/endpoints/workspaces'
import { tokenStore } from '../../api/tokens'
import type { CheckoutPreview, MerchantStatement, Order } from '../../api'
import { cart } from '../../cart/cart'
import { makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/workspaces')
vi.mock('../../api/endpoints/commerce')
vi.mock('../../api/endpoints/reference')

const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

function order(extra: Partial<Order> = {}): Order {
  return {
    id: 'o-1',
    number: 'RCH-1',
    checkout_number: 'CHK-1',
    channel: 'B2C',
    status: 'SHIPPED',
    payment_method: 'CASH_ON_DELIVERY',
    payment_status: 'UNPAID',
    currency: 'IQD',
    list_total: '100000',
    seller_discount_total: '10000',
    platform_discount_total: '0',
    total: '90000',
    refunded_total: '0',
    merchant: { id: 'm-1', name: 'Rehab store' },
    buyer_name: 'Sara',
    delivery_governorate: { id: 'g', name_ar: 'بغداد', name_en: 'Baghdad' },
    delivery_city: null,
    delivery_address: 'Karrada',
    contact_phone: '07700000000',
    note: '',
    shipping_reference: 'COURIER-1',
    paid_at: null,
    shipped_at: '2026-11-05T10:00:00Z',
    delivered_at: null,
    completed_at: null,
    items: [
      {
        id: 'i-1', product_id: 'p-1', image_url: '', title_snapshot: 'Knee walker', unit_price: '100000', quantity: 1, line_total: '100000',
        seller_discount: '10000', platform_discount: '0', buyer_paid: '90000', refunded_quantity: 0, refunded_buyer_paid: '0',
      },
    ],
    transitions: [],
    returns: [],
    disputes: [],
    refunds: [],
    return_deadline: null,
    created_at: '2026-11-05T09:00:00Z',
    status_changed_at: null,
    ...extra,
  }
}

const preview = (coupon: string | null): CheckoutPreview => ({
  currency: 'IQD',
  orders: [
    { merchant: { id: 'm-1', name: 'Rehab store' }, seller_coupon: null, lines: [], list_total: '100000', seller_discount_total: '0', platform_discount_total: coupon ? '10000' : '0', total: coupon ? '90000' : '100000' },
    { merchant: { id: 'm-2', name: 'Aman' }, seller_coupon: null, lines: [], list_total: '25000', seller_discount_total: '0', platform_discount_total: '0', total: '25000' },
  ],
  platform_coupon: coupon,
  list_total: '125000',
  seller_discount_total: '0',
  platform_discount_total: coupon ? '10000' : '0',
  total: coupon ? '115000' : '125000',
})

beforeEach(() => {
  vi.resetAllMocks()
  tokenStore.clear()
  cart.clear()
  vi.mocked(referenceApi.listGovernorates).mockResolvedValue([])
  vi.mocked(workspacesApi.listMyOrders).mockResolvedValue(page([]))
  vi.mocked(workspacesApi.getDeliveryDefaults).mockResolvedValue({ governorate: null, city: null, address: '', phone: '' })
})

function signIn(extra = {}) {
  tokenStore.set({ access: 'a', refresh: 'r' })
  vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PATIENT', email_verified: true, ...extra }))
}

describe('marketplace', () => {
  it('one checkout for two stores: the server prices it and a Racheeta coupon is re-priced by the server', async () => {
    signIn()
    cart.add({ product: 'p-1', title: 'Chair', price: '100000', currency: 'IQD', merchantId: 'm-1', merchantName: 'Rehab store' }, 1)
    cart.add({ product: 'p-2', title: 'Oximeter', price: '25000', currency: 'IQD', merchantId: 'm-2', merchantName: 'Aman' }, 1)
    vi.mocked(workspacesApi.getStoreProduct).mockImplementation(async (id) => ({ id, price: id === 'p-1' ? '100000' : '25000', in_stock: true }) as never)
    vi.mocked(commerceApi.previewCheckout).mockImplementation(async (_items, coupons) => preview(coupons[0] ?? null))
    renderApp('/cart')
    const panel = await screen.findByTestId('checkout-panel')
    await waitFor(() => expect(within(panel).getByTestId('checkout-total')).toHaveTextContent(/125[,٬]?000/))
    expect(within(panel).getAllByTestId('money-table')).toHaveLength(2) // one order per store
    await userEvent.type(within(panel).getByRole('textbox', { name: /رمز القسيمة|coupon code/i }), 'racheeta10k')
    await userEvent.click(within(panel).getByRole('button', { name: /^تطبيق$|^apply$/i }))
    await waitFor(() => expect(within(panel).getByTestId('checkout-total')).toHaveTextContent(/115[,٬]?000/))
    expect(vi.mocked(commerceApi.previewCheckout).mock.calls.at(-1)![1]).toEqual(['RACHEETA10K'])
  })

  it('a buyer confirms receipt of a shipped order; nothing about the commission is shown to buyers', async () => {
    signIn()
    vi.mocked(workspacesApi.listMyOrders).mockResolvedValue(page([order()]))
    vi.mocked(commerceApi.confirmDelivery).mockResolvedValue(order({ status: 'DELIVERED' }))
    renderApp('/orders')
    const group = await screen.findByTestId('checkout-group')
    expect(within(group).queryByText(/عمولة|commission/i)).toBeNull()
    await userEvent.click(within(group).getByRole('button', { name: /استلمت الطلب|i received it/i }))
    await waitFor(() => expect(commerceApi.confirmDelivery).toHaveBeenCalledWith('o-1'))
  })

  it('the seller statement shows the 20% commission and what Racheeta owes', async () => {
    signIn({ role: 'MEDICAL_COMPANY' })
    const statement: MerchantStatement = {
      currency: 'IQD', commission_rate: '20.00', gross_sales: '100000', seller_discounts: '10000', merchandise_net: '90000',
      commission: '18000', refunded_commission: '0', refunded_seller_payable: '0', seller_earnings: '72000', paid_out: '0',
      payable: '72000', receivable: '0', recovered: '0', pending_orders: 0, pending_seller_payable: '0', draft_settlement: null, entries: [], settlements: [],
    }
    vi.mocked(commerceApi.getStatement).mockResolvedValue(statement)
    renderApp('/merchant/center?tab=finance')
    const cards = await screen.findByTestId('statement-cards')
    expect(within(cards).getByText(/18[,٬]?000/)).toBeInTheDocument()
    expect(within(cards).getAllByText(/72[,٬]?000/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByTestId('seller-nav')).toBeInTheDocument()
    expect(within(cards).queryByText(/مستحق لراشيتة عليك|you owe racheeta/i)).toBeNull()
  })

  it('a refund after payout shows what the seller owes Racheeta, never a negative payable', async () => {
    signIn({ role: 'MEDICAL_COMPANY' })
    vi.mocked(commerceApi.getStatement).mockResolvedValue({
      currency: 'IQD', commission_rate: '20.00', gross_sales: '100000', seller_discounts: '0', merchandise_net: '100000',
      commission: '20000', refunded_commission: '20000', refunded_seller_payable: '80000', seller_earnings: '0', paid_out: '80000',
      payable: '0', receivable: '80000', recovered: '0', pending_orders: 0, pending_seller_payable: '0', draft_settlement: null,
      entries: [], settlements: [],
    })
    renderApp('/merchant/center?tab=finance')
    const cards = await screen.findByTestId('statement-cards')
    expect(within(cards).getByText(/مستحق لراشيتة عليك|you owe racheeta/i)).toBeInTheDocument()
    expect(within(cards).queryByText(/−\s*\d|-\d/)).toBeNull()
  })

  it('staff without the finance permission see a clear refusal in the finance console', async () => {
    signIn({ role: 'ADMIN', is_staff: true })
    vi.mocked(commerceApi.listAdminOrders).mockRejectedValue(new ApiError(403, 'permission_denied', 'Racheeta finance only.'))
    renderApp('/admin-finance')
    expect(await screen.findByText(/ليست لديك صلاحية|do not have permission/i)).toBeInTheDocument()
  })
})
