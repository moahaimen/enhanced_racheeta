import { useTranslation } from 'react-i18next'

import type { StoreProduct } from '../../api'
import { Badge } from '../../design-system'
import { MAX_CART_QUANTITY } from '../../cart/cart'
import styles from './store.module.css'

export function QuantityStepper({ value, onChange, max = MAX_CART_QUANTITY }: { value: number; onChange: (next: number) => void; max?: number }) {
  const { t } = useTranslation()
  return (
    <div className={styles.stepper} role="group" aria-label={t('store.quantity')}>
      <button type="button" onClick={() => onChange(value - 1)} disabled={value <= 1} aria-label={t('store.decrease')}>
        −
      </button>
      <output aria-live="polite">{value}</output>
      <button type="button" onClick={() => onChange(value + 1)} disabled={value >= max} aria-label={t('store.increase')}>
        +
      </button>
    </div>
  )
}

export function StockBadge({ product }: { product: Pick<StoreProduct, 'in_stock' | 'low_stock'> }) {
  const { t } = useTranslation()
  if (!product.in_stock) return <Badge tone="neutral">{t('store.outOfStock')}</Badge>
  if (product.low_stock) return <Badge tone="warning">{t('store.fewLeft')}</Badge>
  return <Badge tone="success">{t('store.inStock')}</Badge>
}
