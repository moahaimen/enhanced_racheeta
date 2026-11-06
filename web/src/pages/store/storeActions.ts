import type { PublicVariant, StoreProduct } from '../../api'
import { cart } from '../../cart/cart'

export function addToCart(product: StoreProduct, quantity: number, variant?: PublicVariant | null) {
  cart.add(
    {
      product: product.id,
      ...(variant ? { variant: variant.id, variantLabel: variant.label } : {}),
      title: product.title,
      price: (variant?.price ?? product.price) as string,
      currency: product.currency,
      merchantId: product.company.id,
      merchantName: product.company.name,
      image: product.images?.[0]?.url || product.image_url || '',
    },
    quantity,
  )
}

export function formatPrice(value: string | number, currency: string, language: string) {
  return `${Number(value).toLocaleString(language)} ${currency}`
}
