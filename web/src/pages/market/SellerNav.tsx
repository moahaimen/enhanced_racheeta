import { useTranslation } from 'react-i18next'
import { NavLink, useSearchParams } from 'react-router'

import { Icon, type IconName } from '../../design-system'

const LINKS: { id: string; to: string; icon: IconName }[] = [
  { id: 'orders', to: '/merchant/orders', icon: 'box' },
  { id: 'returns', to: '/merchant/center?tab=returns', icon: 'refresh' },
  { id: 'inventory', to: '/merchant/center?tab=inventory', icon: 'clipboard' },
  { id: 'promotions', to: '/merchant/center?tab=promotions', icon: 'tag' },
  { id: 'finance', to: '/merchant/center?tab=finance', icon: 'calculator' },
  { id: 'quotes', to: '/merchant/quotes', icon: 'mail' },
]

/** Seller center navigation; keeps `?company=` so staff stay in the business they work for. */
export function SellerNav({ active }: { active: string }) {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const company = params.get('company')
  const withCompany = (to: string) => (company ? `${to}${to.includes('?') ? '&' : '?'}company=${encodeURIComponent(company)}` : to)
  return (
    <nav aria-label={t('market.sellerCenter')} className="cluster" style={{ marginBlock: 'var(--space-3)' }} data-testid="seller-nav">
      {LINKS.map((link) => (
        <NavLink
          key={link.id}
          to={withCompany(link.to)}
          aria-current={active === link.id ? 'page' : undefined}
          className={`seller-nav-link${active === link.id ? ' is-active' : ''}`}
        >
          <Icon name={link.icon} size={16} /> {t(`market.nav.${link.id}`)}
        </NavLink>
      ))}
    </nav>
  )
}
