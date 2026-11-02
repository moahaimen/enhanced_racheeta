import type { StoreProduct } from '../../api'
import { cart } from '../../cart/cart'

export function addToCart(product: StoreProduct, quantity: number) {
  cart.add(
    {
      product: product.id,
      title: product.title,
      price: product.price,
      currency: product.currency,
      merchantId: product.company.id,
      merchantName: product.company.name,
      image: product.image_url ?? '',
    },
    quantity,
  )
}

export function formatPrice(value: string | number, currency: string, language: string) {
  return `${Number(value).toLocaleString(language)} ${currency}`
}
