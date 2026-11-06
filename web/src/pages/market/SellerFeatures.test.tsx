import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../../api/endpoints/auth'
import * as commerceApi from '../../api/endpoints/commerce'
import * as marketplaceApi from '../../api/endpoints/marketplace'
import * as providersApi from '../../api/endpoints/providers'
import * as referenceApi from '../../api/endpoints/reference'
import * as workspacesApi from '../../api/endpoints/workspaces'
import { tokenStore } from '../../api/tokens'
import type { CheckoutPreview, InvoiceDocument, MedicalCompany, Order, SalesReport, SellerDocument, StoreProduct } from '../../api'
import { cart, lineKey } from '../../cart/cart'
import { makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/workspaces')
vi.mock('../../api/endpoints/commerce')
vi.mock('../../api/endpoints/reference')
vi.mock('../../api/endpoints/marketplace')
vi.mock('../../api/endpoints/providers')

const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

function signIn(extra = {}) {
  tokenStore.set({ access: 'a', refresh: 'r' })
  vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role: 'PATIENT', email_verified: true, ...extra }))
}

const scrubs: StoreProduct = {
  id: 'p-1',
  title: 'Scrubs (demo)',
  description: '',
  brand: '',
  model_name: '',
  price: '20000.00',
  currency: 'IQD',
  in_stock: true,
  low_stock: false,
  images: [
    { id: 'img-1', url: '/api/v1/marketplace/images/img-1', width: 120, height: 90, alt_text: 'front', sort_order: 0 },
    { id: 'img-2', url: '/api/v1/marketplace/images/img-2', width: 120, height: 90, alt_text: 'back', sort_order: 1 },
  ],
  variants: [
    { id: 'v-s', sku: 'SCRUB-S', label: 'Size S', price: '20000.00', in_stock: false, low_stock: false },
    { id: 'v-l', sku: 'SCRUB-L', label: 'Size L', price: '25000.00', in_stock: true, low_stock: true },
  ],
  category: { id: 'c', slug: 'otc', name_ar: 'عناية', name_en: 'Care', buyer_notice_ar: 'للاستعمال تحت الإشراف', buyer_notice_en: 'Use under supervision', max_order_quantity: 3 },
  company: { id: 'm-1', name: 'Aman supplies' },
}

function order(extra: Partial<Order> = {}): Order {
  return {
    id: 'o-1', number: 'RCH-1', checkout_number: 'CHK-1', channel: 'B2C', status: 'SHIPPED', payment_method: 'CASH_ON_DELIVERY',
    payment_status: 'PAID', currency: 'IQD', list_total: '100000', seller_discount_total: '0', platform_discount_total: '0', total: '115000',
    refunded_total: '0', merchant: { id: 'm-1', name: 'Bed store' }, buyer_name: 'Sara',
    delivery_governorate: { id: 'g', name_ar: 'بغداد', name_en: 'Baghdad' }, delivery_city: null, delivery_address: 'Karrada',
    contact_phone: '07700000000', note: '', shipping_reference: 'TRK-9', courier_name: 'Demo courier', shipping_total: '5000',
    tax_mode: 'EXCLUSIVE', tax_rate: '10.00', tax_label: 'Sales tax (demo)', tax_total: '10000', tax_included_total: '0',
    tracking_events: [{ id: 't-1', status: 'OUT_FOR_DELIVERY', note: '', location: 'Karrada', created_at: '2026-11-06T09:00:00Z' }],
    invoices: [{ id: 'inv-1', kind: 'INVOICE', number: 'INV-1', total: '115000', created_at: '2026-11-06T08:00:00Z' }],
    paid_at: '2026-11-06T08:00:00Z', shipped_at: '2026-11-06T08:30:00Z', delivered_at: null, completed_at: null,
    items: [
      { id: 'i-1', kind: 'MERCHANDISE', product_id: 'p-1', variant_id: null, sku_snapshot: 'BED-1', variant_label_snapshot: '', image_url: '', title_snapshot: 'Home-care bed', unit_price: '100000', quantity: 1, line_total: '100000', seller_discount: '0', platform_discount: '0', buyer_paid: '100000', refunded_quantity: 0, refunded_buyer_paid: '0' },
      { id: 'i-2', kind: 'TAX', product_id: null, parent_item_id: 'i-1', image_url: '', title_snapshot: 'Sales tax (demo)', unit_price: '10000', quantity: 1, line_total: '10000', seller_discount: '0', platform_discount: '0', buyer_paid: '10000', refunded_quantity: 0, refunded_buyer_paid: '0' },
      { id: 'i-3', kind: 'SHIPPING', product_id: null, image_url: '', title_snapshot: 'Delivery', unit_price: '5000', quantity: 1, line_total: '5000', seller_discount: '0', platform_discount: '0', buyer_paid: '5000', refunded_quantity: 0, refunded_buyer_paid: '0' },
    ],
    transitions: [], returns: [], disputes: [], refunds: [], return_deadline: null, created_at: '2026-11-06T07:00:00Z', status_changed_at: null,
    ...extra,
  }
}

const store = (extra: Partial<MedicalCompany> = {}): MedicalCompany => ({
  id: 'm-1', name: 'Demo pharmacy store', description: '', phone: '', public_email: '', website: '',
  governorate: { id: 'g', slug: 'baghdad', name_ar: 'بغداد', name_en: 'Baghdad' } as never, city: null, address: '',
  verification_status: 'VERIFIED', verification_note: '', verification_requested_at: null, verification_changed_at: null, verified_at: null,
  can_publish: true, identity_locked: true, business_type: 'PHARMACY', can_sell: false, facility_id: 'f-1', store_status: 'INACTIVE',
  required_documents: ['PHARMACY_LICENSE', 'OWNER_ID'], missing_documents: ['OWNER_ID'], tax_mode: 'NONE', tax_rate: '0.00',
  created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z',
  ...extra,
})

const doc = (extra: Partial<SellerDocument> = {}): SellerDocument => ({
  id: 'd-1', kind: 'PHARMACY_LICENSE', original_name: 'licence.pdf', content_type: 'application/pdf', size: 2048, sha256: 'a'.repeat(64),
  reference_number: 'PH-001', expires_on: null, status: 'APPROVED', review_note: '', reviewed_at: null, created_at: '2026-11-01T00:00:00Z',
  file_url: '/api/v1/marketplace/company/documents/d-1/file', ...extra,
})

beforeEach(() => {
  vi.resetAllMocks()
  tokenStore.clear()
  cart.clear()
  vi.mocked(referenceApi.listGovernorates).mockResolvedValue([])
  vi.mocked(workspacesApi.listMyOrders).mockResolvedValue(page([]))
  vi.mocked(workspacesApi.getDeliveryDefaults).mockResolvedValue({ governorate: null, city: null, address: '', phone: '' })
})

describe('products with options (variants) and photos', () => {
  it('the buyer picks an option with its own price; the cart keeps one line per option', async () => {
    vi.mocked(workspacesApi.getStoreProduct).mockResolvedValue(scrubs)
    renderApp('/store/p-1')
    const picker = await screen.findByTestId('variant-picker')
    // The first IN-STOCK option is preselected (Size S is out of stock).
    expect(within(picker).getByRole('radio', { name: /Size L/ })).toBeChecked()
    expect(screen.getByTestId('product-price')).toHaveTextContent(/25[,٬]?000/)
    expect(screen.getByTestId('category-notice')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /الصورة|photo/i })).toHaveLength(2)
    await userEvent.click(screen.getByRole('button', { name: /أضف إلى السلة|add to cart/i }))
    await userEvent.click(within(picker).getByRole('radio', { name: /Size S/ }))
    expect(screen.queryByRole('button', { name: /أضف إلى السلة|add to cart/i })).toBeNull() // out of stock
    const { useCart } = await import('../../cart/cart')
    expect(typeof useCart).toBe('function')
    cart.add({ product: 'p-1', variant: 'v-s', variantLabel: 'Size S', title: 'Scrubs', price: '20000', currency: 'IQD', merchantId: 'm-1', merchantName: 'Aman' }, 1)
    cart.setQuantity(lineKey({ product: 'p-1', variant: 'v-l' }), 2)
    vi.mocked(workspacesApi.getStoreProduct).mockResolvedValue(scrubs)
    renderApp('/cart')
    const labels = await screen.findAllByTestId('cart-variant')
    expect(labels.map((l) => l.textContent)).toEqual([expect.stringContaining('Size L'), expect.stringContaining('Size S')])
  })
})

describe('delivery fees and seller-declared tax', () => {
  it('the cart shows each seller\'s delivery fee and tax from the server, never computed in the browser', async () => {
    signIn()
    cart.add({ product: 'p-1', title: 'Bed', price: '100000', currency: 'IQD', merchantId: 'm-1', merchantName: 'Bed store' }, 1)
    vi.mocked(workspacesApi.getStoreProduct).mockResolvedValue({ ...scrubs, id: 'p-1', variants: [], price: '100000' })
    const priced: CheckoutPreview = {
      currency: 'IQD', platform_coupon: null, list_total: '100000', seller_discount_total: '0', platform_discount_total: '0',
      merchandise_total: '100000', shipping_known: true, shipping_total: '5000', tax_total: '10000', total: '115000',
      orders: [{
        merchant: { id: 'm-1', name: 'Bed store' }, seller_coupon: null, lines: [], list_total: '100000', seller_discount_total: '0',
        platform_discount_total: '0', merchandise_total: '100000', shipping_fee: '5000', shipping_min_days: 1, shipping_max_days: 3,
        tax_mode: 'EXCLUSIVE', tax_rate: '10.00', tax_label: 'Sales tax (demo)', tax_total: '10000', tax_included_total: '0', total: '115000',
      }],
    }
    vi.mocked(commerceApi.previewCheckout).mockResolvedValue(priced)
    renderApp('/cart')
    const panel = await screen.findByTestId('checkout-panel')
    await waitFor(() => expect(within(panel).getByTestId('checkout-total')).toHaveTextContent(/115[,٬]?000/))
    expect(within(panel).getByText(/رسوم التوصيل|delivery fee/i)).toBeInTheDocument()
    expect(within(panel).getByText(/Sales tax \(demo\) \(10%\)/)).toBeInTheDocument()
    // Only ids, options and quantities are sent.
    expect(vi.mocked(commerceApi.previewCheckout).mock.calls[0]![0]).toEqual([{ product: 'p-1', quantity: 1 }])
  })

  it('an order shows delivery, tax, tracking and its printable documents; buyers never see the commission', async () => {
    signIn()
    vi.mocked(workspacesApi.listMyOrders).mockResolvedValue(page([order()]))
    renderApp('/orders')
    const group = await screen.findByTestId('checkout-group')
    expect(within(group).getAllByTestId('order-item')).toHaveLength(1) // charges are totals, not products
    expect(within(group).getByTestId('order-tracking')).toHaveTextContent(/Demo courier/)
    expect(within(group).getByText(/خرجت للتوصيل|out for delivery/i)).toBeInTheDocument()
    expect(within(group).getByTestId('order-documents')).toHaveTextContent('INV-1')
    expect(within(group).queryByText(/عمولة|commission/i)).toBeNull()
  })

  it('the printable invoice renders only the frozen server snapshot', async () => {
    signIn()
    const invoice: InvoiceDocument = {
      id: 'inv-1', kind: 'INVOICE', number: 'INV-1', total: '115000', created_at: '2026-11-06T08:00:00Z',
      snapshot: {
        kind: 'INVOICE', issued_at: '2026-11-06T08:00:00Z', currency: 'IQD', notice: 'Local demonstration document.', operator: 'Racheeta',
        seller: { name: 'Bed store', business_type: 'EQUIPMENT_SUPPLIER', address: 'Street 1', governorate: 'Baghdad', phone: '', email: '', tax_registration_number: 'TAX-DEMO-1' },
        buyer: { name: 'Sara', address: 'Karrada', governorate: 'Baghdad', city: '', phone: '07700000000' },
        order: { number: 'RCH-1', checkout: 'CHK-1', placed_at: '2026-11-06T07:00:00Z', channel: 'B2C', payment_method: 'CASH_ON_DELIVERY', payment_reference: 'SIM-1', paid_at: '2026-11-06T08:00:00Z' },
        lines: [{ title: 'Home-care bed', variant: '', sku: 'BED-1', quantity: 1, unit_price: '100000.00', line_total: '100000.00', seller_discount: '0.00', platform_discount: '0.00', tax: '10000.00', total: '110000.00', refunded_quantity: 0 }],
        tax: { mode: 'EXCLUSIVE', rate: '10.00', label: 'Sales tax (demo)', added: '10000.00', included: '0.00' },
        totals: { list: '100000.00', seller_discount: '0.00', platform_discount: '0.00', shipping: '5000.00', tax: '10000.00', total: '115000.00', refunded: '0.00' },
      },
    }
    vi.mocked(commerceApi.listMyInvoices).mockResolvedValue([invoice])
    vi.mocked(commerceApi.getMyInvoice).mockResolvedValue(invoice)
    renderApp('/orders/o-1/documents')
    const sheet = await screen.findByTestId('printable-document')
    expect(within(sheet).getByText('Home-care bed')).toBeInTheDocument()
    expect(within(sheet).getByText('TAX-DEMO-1')).toBeInTheDocument()
    expect(within(sheet).getAllByText(/115[,٬]?000/).length).toBeGreaterThan(0)
    expect(within(sheet).queryByText(/عمولة|commission/i)).toBeNull()
    expect(within(sheet).getByTestId('print-document')).toBeInTheDocument()
  })
})

describe('seller onboarding', () => {
  it('a pharmacy without a store is offered to open one (it stays a provider)', async () => {
    signIn({ role: 'PROVIDER', account_type: 'PHARMACY' })
    vi.mocked(providersApi.getMyProvider).mockResolvedValue({ provider_type: 'PHARMACY' } as never)
    const { ApiError } = await import('../../api/client')
    vi.mocked(marketplaceApi.getMyCompany).mockRejectedValue(new ApiError(404, 'not_found', 'none'))
    vi.mocked(marketplaceApi.listCategories).mockResolvedValue([])
    vi.mocked(marketplaceApi.openPharmacyStore).mockResolvedValue(store())
    renderApp('/company')
    const start = await screen.findByTestId('pharmacy-store-start')
    await userEvent.click(within(start).getByRole('button', { name: /افتح متجر صيدليتي|open my pharmacy store/i }))
    await waitFor(() => expect(marketplaceApi.openPharmacyStore).toHaveBeenCalled())
  })

  it('a doctor (not a pharmacy) is kept away from the store pages', async () => {
    signIn({ role: 'PROVIDER' })
    vi.mocked(providersApi.getMyProvider).mockResolvedValue({ provider_type: 'DOCTOR' } as never)
    renderApp('/company')
    expect(await screen.findByTestId('role-denied')).toBeInTheDocument()
    expect(marketplaceApi.getMyCompany).not.toHaveBeenCalled()
  })

  it('store setup lists the steps, the documents and refuses activation while a document is missing', async () => {
    signIn({ role: 'MEDICAL_COMPANY' })
    vi.mocked(marketplaceApi.getStore).mockResolvedValue(store())
    vi.mocked(marketplaceApi.listDocuments).mockResolvedValue([doc(), doc({ id: 'd-2', kind: 'OTHER', status: 'REJECTED', review_note: 'Unreadable' })])
    renderApp('/merchant/center?tab=setup')
    const steps = await screen.findByTestId('onboarding-steps')
    expect(steps).toHaveTextContent(/1|مستند واحد/)
    expect(screen.getByTestId('required-documents')).toBeInTheDocument()
    expect(within(screen.getByTestId('seller-documents')).getByText('Unreadable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /تفعيل المتجر|activate store/i })).toBeDisabled()
    expect(screen.getByTestId('document-upload')).toBeInTheDocument()
  })

  it('the seller report shows the settled 20% commission and offers a CSV download', async () => {
    signIn({ role: 'MEDICAL_COMPANY' })
    const report: SalesReport = {
      company_id: 'm-1', from: '2026-08-08', to: '2026-11-06', currency: 'IQD', commission_note: 'Commission is 20% of merchandise.',
      orders: [{ order: 'RCH-1', placed: '2026-11-06', completed: '2026-11-06', status: 'COMPLETED', payment: 'PAID', list: '100000', seller_discount: '0', merchandise_net: '100000', commission: '20000', shipping: '5000', tax: '0', refunded: '0', earnings: '85000', settled: 'yes' }],
      totals: { orders: 1, merchandise_net: '100000', settled_commission: '20000', settled_shipping: '5000', settled_tax: '0', refunded: '0', settled_earnings: '85000', paid_out: '0' },
      months: [{ month: '2026-11', orders: 1, merchandise_net: '100000', commission: '20000', earnings: '85000', paid_out: '0' }],
      balances: { payable: '85000', receivable: '0' },
    }
    vi.mocked(commerceApi.getSalesReport).mockResolvedValue(report)
    renderApp('/merchant/center?tab=reports')
    const cards = await screen.findByTestId('report-cards')
    expect(within(cards).getByText(/20[,٬]?000/)).toBeInTheDocument()
    expect(within(cards).getAllByText(/85[,٬]?000/).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /تنزيل CSV|download csv/i })).toBeInTheDocument()
    expect(screen.getByTestId('report-orders')).toHaveTextContent('RCH-1')
  })

  it('Racheeta administrators review documents and verify sellers', async () => {
    signIn({ role: 'ADMIN', is_staff: true })
    vi.mocked(marketplaceApi.listAdminCompanies).mockResolvedValue({ count: 1, results: [{ ...store({ verification_status: 'PENDING' }), account_email: 'seller@example.com' }] })
    vi.mocked(marketplaceApi.listCompanyDocumentsAdmin).mockResolvedValue({ count: 1, results: [doc({ status: 'PENDING' })] })
    vi.mocked(marketplaceApi.decideSellerDocument).mockResolvedValue(doc())
    renderApp('/admin-console?tab=sellers')
    const docs = await screen.findByTestId('admin-documents')
    await userEvent.click(within(docs).getByRole('button', { name: /^قبول$|^approve$/i }))
    await waitFor(() => expect(marketplaceApi.decideSellerDocument).toHaveBeenCalledWith('d-1', true))
    expect(screen.getByRole('button', { name: /^تحقق$|^verify$/i })).toBeInTheDocument()
  })
})
