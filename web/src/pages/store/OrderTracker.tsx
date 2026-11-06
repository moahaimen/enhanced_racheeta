import { useTranslation } from 'react-i18next'

import type { OrderStatus } from '../../api'
import { Icon } from '../../design-system'
import styles from './cart.module.css'

const STEPS: OrderStatus[] = ['PLACED', 'CONFIRMED', 'SHIPPED', 'DELIVERED', 'COMPLETED']

/** Progress of a store order: placed → accepted → shipped → delivered → completed (or cancelled). */
export function OrderTracker({ status }: { status: OrderStatus }) {
  const { t } = useTranslation()
  if (status === 'CANCELLED') {
    return (
      <p className={styles.cancelled} data-testid="order-tracker">
        <Icon name="x" size={16} /> {t('market.orderStatus.CANCELLED')}
      </p>
    )
  }
  const reached = STEPS.indexOf(status)
  return (
    <ol className={styles.tracker} data-testid="order-tracker" aria-label={t('store.orderProgress')}>
      {STEPS.map((step, index) => (
        <li key={step} className={index <= reached ? styles.done : undefined} aria-current={index === reached ? 'step' : undefined}>
          <span className={styles.dot}>{index < reached || status === 'COMPLETED' ? <Icon name="check" size={12} /> : index + 1}</span>
          <span>{t(`market.orderStatus.${step}`)}</span>
        </li>
      ))}
    </ol>
  )
}
