import type { OrderStatus, ReturnStatus, StorePaymentStatus } from '../../api'
import type { BadgeTone } from '../../design-system'

export const ORDER_TONE: Record<OrderStatus, BadgeTone> = {
  PLACED: 'warning',
  CONFIRMED: 'brand',
  SHIPPED: 'brand',
  DELIVERED: 'success',
  COMPLETED: 'success',
  CANCELLED: 'neutral',
}
export const PAYMENT_TONE: Record<StorePaymentStatus, BadgeTone> = {
  UNPAID: 'neutral',
  PAID: 'success',
  REFUND_PENDING: 'warning',
  PARTIALLY_REFUNDED: 'warning',
  REFUNDED: 'neutral',
}
export const RETURN_TONE: Record<ReturnStatus, BadgeTone> = {
  REQUESTED: 'warning',
  APPROVED: 'brand',
  REJECTED: 'neutral',
  RECEIVED: 'brand',
  REFUNDED: 'success',
}
