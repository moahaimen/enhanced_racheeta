import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'

import { marketplace as marketplaceApi } from '../../api'
import type { MarketplaceProduct, ProductCategory } from '../../api'
import {
  Container,
  EmptyState,
  ErrorState,
  Icon,
  LinkButton,
  LoadingState,
  PageHeader,
  PageStack,
  Pagination,
  ProductImage,
  SectionCard,
  Select,
} from '../../design-system'
import storeStyles from '../store/store.module.css'
import { useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { SponsoredSection } from '../advertising/SponsoredSection'

const PAGE_SIZE = 20

export function formatProductPrice(product: Pick<MarketplaceProduct, 'price' | 'currency'>, language: string, onRequest: string) {
  if (product.price === null) return onRequest
  return `${Number(product.price).toLocaleString(language)} ${product.currency}`
}

/**
 * /marketplace — products the BACKEND targets at this provider. The page never
 * filters by audience itself: what the API returns is exactly what is shown.
 */
export function MarketplacePage() {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const category = params.get('category') ?? ''
  const categories = useAsyncData<ProductCategory[]>((signal) => marketplaceApi.listCategories(signal), [])
  const products = useAsyncData(
    (signal) => marketplaceApi.listTargetedProducts(page, category, signal),
    [page, category],
  )

  const setQuery = (next: { page?: number; category?: string }) => {
    const out = new URLSearchParams()
    const c = next.category ?? category
    const p = next.page ?? 1
    if (c) out.set('category', c)
    if (p > 1) out.set('page', String(p))
    setParams(out)
  }

  return (
    <Container width="xl">
      <PageHeader
        eyebrow={<><Icon name="cart" size={16} />{t('modules.marketplace')}</>}
        title={t('marketplace.title')}
        description={t('marketplace.intro')}
        actions={
          categories.data ? (
            <Select label={t('marketplace.category')} value={category} onChange={(e) => setQuery({ category: e.target.value, page: 1 })}>
              <option value="">{t('marketplace.allCategories')}</option>
              {categories.data.map((c) => (
                <option key={c.id} value={c.id}>
                  {name(c)}
                </option>
              ))}
            </Select>
          ) : null
        }
      />
      <PageStack>
        <SponsoredSection />
        <SectionCard title={t('marketplace.forYou')} description={t('marketplace.targetingNote')} headingLevel={2}>
          {products.loading ? (
            <LoadingState testId="marketplace-loading" />
          ) : products.error ? (
            <ErrorState error={products.error} onRetry={products.reload} />
          ) : (products.data?.results ?? []).length === 0 ? (
            <EmptyState icon="cart" title={t('marketplace.empty')} testId="marketplace-empty" />
          ) : (
            <ul className={storeStyles.grid} style={{ listStyle: 'none', padding: 0, margin: 0 }} data-testid="marketplace-results">
              {(products.data?.results ?? []).map((product) => (
                <li key={product.id} className={storeStyles.card} data-testid="marketplace-product">
                  <Link to={`/marketplace/products/${product.id}`} className={storeStyles.imageLink} tabIndex={-1} aria-hidden="true">
                    <ProductImage src={product.image_url} alt={product.title} />
                  </Link>
                  <span className={storeStyles.category}>{name(product.category)}</span>
                  <h3 className={storeStyles.title}>
                    <Link to={`/marketplace/products/${product.id}`}>{product.title}</Link>
                  </h3>
                  <div className={storeStyles.seller}>
                    {product.company.name}
                    {product.brand ? ` · ${product.brand}` : ''}
                    {product.model_name ? ` · ${product.model_name}` : ''}
                  </div>
                  <div className={storeStyles.price} dir="auto">
                    {formatProductPrice(product, i18n.language, t('marketplace.priceOnRequest'))}
                  </div>
                  <LinkButton to={`/marketplace/products/${product.id}`} size="sm" variant="secondary">
                    {t('quotes.request')}
                  </LinkButton>
                </li>
              ))}
            </ul>
          )}
          {products.data ? (
            <Pagination
              page={page}
              total={Math.max(1, Math.ceil(products.data.count / PAGE_SIZE))}
              hasNext={products.data.next !== null}
              hasPrevious={products.data.previous !== null}
              onChange={(next) => setQuery({ page: next })}
            />
          ) : null}
        </SectionCard>
      </PageStack>
    </Container>
  )
}
