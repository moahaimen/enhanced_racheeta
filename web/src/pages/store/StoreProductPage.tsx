import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'

import { workspaces as api } from '../../api'
import { Alert, AsyncPage, Button, Container, Icon, LinkButton, ProductImage } from '../../design-system'
import { pickScript, useLocalizedName } from '../../i18n/localized'
import { useCart } from '../../cart/cart'
import { QuantityStepper, StockBadge } from './StoreParts'
import { addToCart, formatPrice } from './storeActions'
import styles from './store.module.css'

/** /store/:id — one consumer product. Unknown, restricted or B2B-only ids are a 404 from the server. */
export function StoreProductPage() {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const { id = '' } = useParams()
  const [qty, setQty] = useState(1)
  const [added, setAdded] = useState(false)
  const lines = useCart()
  return (
    <Container width="xl">
      <AsyncPage load={(signal) => api.getStoreProduct(id, signal)} deps={[id]}>
        {(product) => {
          const title = pickScript(product.title, i18n.language)
          const inCart = lines.find((line) => line.product === product.id)?.quantity ?? 0
          return (
            <article className={styles.detail} data-testid="store-product">
              <ProductImage src={product.image_url} alt={title} size="lg" />
              <div className={styles.detailInfo}>
                <Link to={`/store?category=${encodeURIComponent(product.category.slug)}`} className={styles.category}>
                  {name(product.category)}
                </Link>
                <h1 className={styles.detailTitle}>{title}</h1>
                <span className={styles.seller}>{t('store.by', { name: pickScript(product.company.name, i18n.language) })}</span>
                <span className={`${styles.detailPrice} ltr`}>{formatPrice(product.price, product.currency, i18n.language)}</span>
                <StockBadge product={product} />
                {product.description ? <p className="prewrap text-secondary">{product.description}</p> : null}
                {product.in_stock ? (
                  <div className={styles.buy}>
                    <QuantityStepper value={qty} onChange={setQty} />
                    <Button
                      leading={<Icon name="cart" size={18} />}
                      onClick={() => {
                        addToCart(product, qty)
                        setAdded(true)
                      }}
                    >
                      {t('store.addToCart')}
                    </Button>
                  </div>
                ) : null}
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
        }}
      </AsyncPage>
    </Container>
  )
}
