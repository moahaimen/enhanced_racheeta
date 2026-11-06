import type { Order, OrderItem } from '../../api'

/** Product lines (delivery and tax are charges, shown in the totals). */
export function merchandise(order: Order): OrderItem[] {
  return order.items.filter((item) => (item.kind ?? 'MERCHANDISE') === 'MERCHANDISE')
}
