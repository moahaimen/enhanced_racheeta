import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { workspaces as api } from '../../api'
import type { StoreProduct } from '../../api'
import {
  Alert,
  AsyncPage,
  Badge,
  Button,
  Container,
  EmptyState,
  Icon,
  LinkButton,
  PageHeader,
  PageStack,
  Pagination,
  SectionCard,
  Select,
} from '../../design-system'
import { useLocalizedName, pickScript } from '../../i18n/localized'
import { cart, useCart } from './cart'

const PAGE_SIZE = 20

/** /store — public consumer store. The BACKEND decides what is sellable here (no restricted items). */
export function StorePage() {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const lines = useCart()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const category = params.get('category') ?? ''
  const count = lines.reduce((n, l) => n + l.quantity, 0)
  return (
    <Container width="xl">
      <PageHeader
        eyebrow={<><Icon name="cart" size={16} />{t('nav.store')}</>}
        title={t('store.title')}
        description={t('store.intro')}
        actions={<LinkButton to="/cart" leading={<Icon name="cart" size={18} />}>{t('nav.cart')} ({count})</LinkButton>}
      />
      <PageStack>
        <Alert kind="info">{t('store.demoPayment')}</Alert>
        <AsyncPage load={(signal) => api.listStoreCategories(signal)}>
          {(categories) => (
            <Select
              label={t('marketplace.category', { defaultValue: 'Category' })}
              value={category}
              onChange={(e) => setParams(e.target.value ? { category: e.target.value } : {})}
            >
              <option value="">{t('store.allCategories')}</option>
              {categories.map((c) => (
                <option key={c.id} value={c.slug}>{name(c)}</option>
              ))}
            </Select>
          )}
        </AsyncPage>
        <AsyncPage load={(signal) => api.listStoreProducts(page, category, signal)} deps={[page, category]}>
          {(result) =>
            result.results.length === 0 ? (
              <div className="card-block"><EmptyState icon="cart" title={t('store.empty')} /></div>
            ) : (
              <>
                <div className="grid-auto" data-testid="store-products">
                  {result.results.map((product) => <StoreCard key={product.id} product={product} />)}
                </div>
                <Pagination
                  page={page}
                  total={Math.max(1, Math.ceil(result.count / PAGE_SIZE))}
                  hasNext={result.next !== null}
                  hasPrevious={result.previous !== null}
                  onChange={(next) => setParams({ ...(category ? { category } : {}), ...(next > 1 ? { page: String(next) } : {}) })}
                />
              </>
            )
          }
        </AsyncPage>
      </PageStack>
    </Container>
  )
}

function StoreCard({ product }: { product: StoreProduct }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const [added, setAdded] = useState(false)
  const title = pickScript(product.title, i18n.language)
  return (
    <SectionCard
      title={title}
      description={t('store.by', { name: pickScript(product.company.name, i18n.language) })}
      headingLevel={2}
      actions={<Badge tone={product.in_stock ? 'success' : 'neutral'}>{product.in_stock ? t('store.inStock') : t('store.outOfStock')}</Badge>}
    >
      <div className="cluster">
        <Badge tone="brand">{name(product.category)}</Badge>
        <strong className="ltr">{Number(product.price).toLocaleString(i18n.language)} {product.currency}</strong>
      </div>
      <Button
        size="sm"
        disabled={!product.in_stock}
        onClick={() => {
          cart.add({
            product: product.id,
            title: product.title,
            price: product.price,
            currency: product.currency,
            merchantId: product.company.id,
            merchantName: product.company.name,
          })
          setAdded(true)
        }}
        data-testid={`add-${product.id}`}
      >
        {added ? t('store.added') : t('store.addToCart')}
      </Button>
    </SectionCard>
  )
}
