import { useTranslation } from 'react-i18next'

import { Icon } from '../../icons'
import { Button } from '../Button/Button'
import styles from './Pagination.module.css'

export interface PaginationProps {
  page: number
  total: number
  hasNext: boolean
  hasPrevious: boolean
  onChange: (page: number) => void
}

export function Pagination({ page, total, hasNext, hasPrevious, onChange }: PaginationProps) {
  const { t } = useTranslation()
  if (total <= 1) return null
  return (
    <nav className={styles.nav} aria-label="pagination">
      <Button variant="ghost" disabled={!hasPrevious} onClick={() => onChange(page - 1)} leading={<Icon name="chevronBack" size={18} flipInRtl />}>
        {t('common.previous')}
      </Button>
      <span className={styles.info} aria-current="page">
        {t('common.page', { page, total })}
      </span>
      <Button variant="ghost" disabled={!hasNext} onClick={() => onChange(page + 1)} trailing={<Icon name="chevronForward" size={18} flipInRtl />}>
        {t('common.next')}
      </Button>
    </nav>
  )
}
