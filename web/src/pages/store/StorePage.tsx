import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'

import { workspaces as api } from '../../api'
import type { StoreProduct } from '../../api'
import { AsyncPage, Button, Container, EmptyState, Icon, Pagination, ProductImage } from '../../design-system'
import { useAsyncData } from '../../hooks/useAsync'
import { pickScript, useLocalizedName } from '../../i18n/localized'
import { useCart, useCartCount } from '../../cart/cart'
import { QuantityStepper, StockBadge } from './StoreParts'
import { addToCart, formatPrice } from './storeActions'
import styles from './store.module.css'

const PAGE_SIZE = 20

/** /store — public consumer store. The BACKEND decides what is sellable here (no restricted items). */
export function StorePage() {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const count = useCartCount()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const category = params.get('category') ?? ''
  const q = params.get('q') ?? ''
  const [query, setQuery] = useState(q)
  const categories = useAsyncData((signal) => api.listStoreCategories(signal), [])
  const go = (next: { category?: string; q?: string; page?: number }) => {
    const merged = { category, q, page: 1, ...next }
    const out: Record<string, string> = {}
    if (merged.category) out.category = merged.category
    if (merged.q) out.q = merged.q
    if (merged.page > 1) out.page = String(merged.page)
    setParams(out)
  }
  return (
    <Container width="xl">
      <section className={styles.hero}>
        <h1 className={styles.heroTitle}>{t('store.title')}</h1>
        <p className={styles.heroText}>{t('store.intro')}</p>
        <form
          className={styles.heroBar}
          role="search"
          onSubmit={(event) => {
            event.preventDefault()
            go({ q: query.trim() })
          }}
        >
          <label className={styles.search}>
            <Icon name="search" size={18} />
            <span className="visually-hidden">{t('store.search')}</span>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('store.searchPlaceholder')} maxLength={80} />
          </label>
          <Link to="/cart" className={styles.cartButton} data-testid="store-cart-link">
            <Icon name="cart" size={18} />
            {t('nav.cart')}
            {count > 0 ? <span className={styles.cartCount}>{count}</span> : null}
          </Link>
        </form>
      </section>
      <p className={styles.notice}>
        <Icon name="info" size={16} />
        {t('store.demoPayment')}
      </p>
      <div className={styles.chips} role="group" aria-label={t('store.categories')}>
        <button type="button" className={styles.chip} aria-pressed={!category} onClick={() => go({ category: '' })}>
          {t('store.allCategories')}
        </button>
        {(categories.data ?? []).map((c) => (
          <button key={c.id} type="button" className={styles.chip} aria-pressed={category === c.slug} onClick={() => go({ category: c.slug })}>
            {name(c)}
          </button>
        ))}
      </div>
      <AsyncPage load={(signal) => api.listStoreProducts(page, category, signal, q)} deps={[page, category, q]}>
        {(result) =>
          result.results.length === 0 ? (
            <div className="card-block">
              <EmptyState icon="cart" title={q ? t('store.noResults', { q }) : t('store.empty')} />
            </div>
          ) : (
            <>
              <p className="text-caption">{t('store.count', { count: result.count })}</p>
              <div className={styles.grid} data-testid="store-products">
                {result.results.map((product) => (
                  <StoreCard key={product.id} product={product} />
                ))}
              </div>
              <Pagination
                page={page}
                total={Math.max(1, Math.ceil(result.count / PAGE_SIZE))}
                hasNext={result.next !== null}
                hasPrevious={result.previous !== null}
                onChange={(next) => go({ page: next })}
              />
            </>
          )
        }
      </AsyncPage>
    </Container>
  )
}

function StoreCard({ product }: { product: StoreProduct }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const [qty, setQty] = useState(1)
  const lines = useCart()
  const inCart = lines.find((line) => line.product === product.id)?.quantity ?? 0
  const title = pickScript(product.title, i18n.language)
  return (
    <article className={styles.card} data-testid="store-card">
      <Link to={`/store/${product.id}`} className={styles.imageLink} tabIndex={-1} aria-hidden="true">
        <ProductImage src={product.images?.[0]?.url || product.image_url} alt={title} />
        <span className={styles.stockBadge}>
          <StockBadge product={product} />
        </span>
      </Link>
      <span className={styles.category}>{name(product.category)}</span>
      <h2 className={styles.title}>
        <Link to={`/store/${product.id}`}>{title}</Link>
      </h2>
      <span className={styles.seller}>{t('store.by', { name: pickScript(product.company.name, i18n.language) })}</span>
      <span className={`${styles.price} ltr`}>{formatPrice(product.price, product.currency, i18n.language)}</span>
      {product.in_stock ? (
        <div className={styles.buy}>
          <QuantityStepper value={qty} onChange={setQty} />
          <Button size="sm" leading={<Icon name="cart" size={16} />} onClick={() => addToCart(product, qty)} data-testid={`add-${product.id}`}>
            {t('store.addToCart')}
          </Button>
        </div>
      ) : (
        <Button size="sm" variant="secondary" disabled>
          {t('store.outOfStock')}
        </Button>
      )}
      {inCart > 0 ? (
        <Link to="/cart" className={styles.inCart}>
          <Icon name="check" size={14} /> {t('store.inCartCount', { count: inCart })}
        </Link>
      ) : null}
    </article>
  )
}
