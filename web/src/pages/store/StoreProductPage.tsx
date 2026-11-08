import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'

import { workspaces as api } from '../../api'
import type { PublicVariant, StoreProduct } from '../../api'
import { Alert, AsyncPage, Button, Container, Icon, LinkButton, ProductImage } from '../../design-system'
import { pickScript, useLocalizedName } from '../../i18n/localized'
import { lineKey, MAX_CART_QUANTITY, useCart } from '../../cart/cart'
import { QuantityStepper, StockBadge } from './StoreParts'
import { addToCart, formatPrice } from './storeActions'
import styles from './store.module.css'

/** /store/:id — one consumer product. Unknown, restricted or B2B-only ids are a 404 from the server. */
export function StoreProductPage() {
  const { id = '' } = useParams()
  return (
    <Container width="xl">
      <AsyncPage load={(signal) => api.getStoreProduct(id, signal)} deps={[id]}>
        {(product) => <ProductDetail key={product.id} product={product} />}
      </AsyncPage>
    </Container>
  )
}

function ProductDetail({ product }: { product: StoreProduct }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const lines = useCart()
  const variants = product.variants ?? []
  // A product with options: the buyer picks one (each has its own price and availability).
  const [variantId, setVariantId] = useState<string | null>(variants.find((v) => v.in_stock)?.id ?? variants[0]?.id ?? null)
  const variant: PublicVariant | null = variants.find((v) => v.id === variantId) ?? null
  const [qty, setQty] = useState(1)
  const [added, setAdded] = useState(false)
  const photos = product.images ?? []
  const [photo, setPhoto] = useState(0)
  const title = pickScript(product.title, i18n.language)
  const key = lineKey({ product: product.id, variant: variant?.id })
  const inCart = lines.find((line) => lineKey(line) === key)?.quantity ?? 0
  const price = variant?.price ?? product.price
  const available = variant ? variant.in_stock : product.in_stock
  const limit = Math.min(MAX_CART_QUANTITY, product.category.max_order_quantity ?? MAX_CART_QUANTITY)
  const notice = i18n.language === 'ar' ? product.category.buyer_notice_ar : product.category.buyer_notice_en
  const mainImage = photos[photo]?.url || product.image_url
  return (
    <article className={styles.detail} data-testid="store-product">
      <div className="stack-sm">
        <ProductImage src={mainImage} alt={photos[photo]?.alt_text || title} size="lg" />
        {photos.length > 1 ? (
          <div className="cluster" role="group" aria-label={t('store.photos')} data-testid="product-photos">
            {photos.map((p, i) => (
              <button
                key={p.id}
                type="button"
                className={`${styles.thumb}${i === photo ? ` ${styles.thumbActive}` : ''}`}
                aria-pressed={i === photo}
                aria-label={t('store.photoN', { n: i + 1 })}
                onClick={() => setPhoto(i)}
              >
                <img src={p.url} alt="" width={56} height={56} loading="lazy" />
              </button>
            ))}
          </div>
        ) : null}
      </div>
      <div className={styles.detailInfo}>
        <Link to={`/store?category=${encodeURIComponent(product.category.slug)}`} className={styles.category}>
          {name(product.category)}
        </Link>
        <h1 className={styles.detailTitle}>{title}</h1>
        <span className={styles.seller}>{t('store.by', { name: pickScript(product.company.name, i18n.language) })}</span>
        <span className={`${styles.detailPrice} ltr`} data-testid="product-price">{formatPrice(price, product.currency, i18n.language)}</span>
        {variants.length ? (
          <fieldset className={styles.options} data-testid="variant-picker">
            <legend>{t('store.chooseOption')}</legend>
            <div className="cluster">
              {variants.map((v) => (
                <label key={v.id} className={`${styles.option}${v.id === variantId ? ` ${styles.optionActive}` : ''}`}>
                  <input
                    type="radio"
                    name="variant"
                    value={v.id}
                    checked={v.id === variantId}
                    onChange={() => {
                      setVariantId(v.id)
                      setAdded(false)
                    }}
                  />
                  <span>{v.label}</span>
                  {!v.in_stock ? <span className="text-caption"> · {t('store.outOfStock')}</span> : null}
                </label>
              ))}
            </div>
          </fieldset>
        ) : null}
        <StockBadge product={variant ? { in_stock: variant.in_stock, low_stock: variant.low_stock } : product} />
        {notice ? (
          <div data-testid="category-notice">
            <Alert kind="info">{notice}</Alert>
          </div>
        ) : null}
        {product.description ? <p className="prewrap text-secondary">{product.description}</p> : null}
        {available ? (
          <div className={styles.buy}>
            <QuantityStepper value={qty} onChange={setQty} max={limit} />
            <Button
              leading={<Icon name="cart" size={18} />}
              onClick={() => {
                addToCart(product, qty, variant)
                setAdded(true)
              }}
            >
              {t('store.addToCart')}
            </Button>
          </div>
        ) : null}
        {product.category.max_order_quantity ? <p className="text-caption">{t('store.maxPerOrder', { count: product.category.max_order_quantity })}</p> : null}
        {added || inCart > 0 ? (
          <Alert kind="success">
            {t('store.inCartCount', { count: inCart })} · <Link to="/cart">{t('store.goToCart')}</Link>
          </Alert>
        ) : null}
        <LinkButton to="/store" variant="ghost" size="sm">
          {t('store.backToStore')}
        </LinkButton>
        <p className="text-caption">{t('store.demoPayment')}</p>
      </div>
    </article>
  )
}
