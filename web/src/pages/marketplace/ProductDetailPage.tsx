import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'

import { ApiError, marketplace as marketplaceApi } from '../../api'
import type { MarketplaceProduct } from '../../api'
import { Alert, AsyncPage, Badge, Button, Container, Icon, PageHeader, PageStack, ProductImage, SectionCard, Select } from '../../design-system'
import { cart } from '../../cart/cart'
import { QuantityStepper } from '../store/StoreParts'
import { RequestQuoteForm } from '../quotes/QuotesPages'
import { useLocalizedName } from '../../i18n/localized'
import { formatProductPrice } from './MarketplacePage'

/** /marketplace/products/:id — the backend applies the same targeting as the list (404 otherwise). */
export function ProductDetailPage() {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const { id = '' } = useParams()
  const load = async (signal: AbortSignal) => {
    try {
      return await marketplaceApi.getTargetedProduct(id, signal)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) throw new ApiError(404, 'not_found', t('marketplace.notFound'))
      throw e
    }
  }
  return (
    <Container width="lg">
      <AsyncPage load={load} deps={[id]}>
        {(product) => (
          <>
            <PageHeader
              eyebrow={
                <Link to="/marketplace" className="cluster">
                  <Icon name="chevronBack" size={14} flipInRtl /> {t('marketplace.title')}
                </Link>
              }
              title={product.title}
              description={[product.brand, product.model_name].filter(Boolean).join(' · ')}
              actions={<Badge tone="brand">{name(product.category)}</Badge>}
            />
            <PageStack>
              <ProductImage src={product.images?.[0]?.url || product.image_url} alt={product.title} size="lg" />
              <SectionCard title={t('marketplace.price')} headingLevel={2}>
                <p className="text-secondary" dir="auto" data-testid="product-price">
                  {formatProductPrice(product, i18n.language, t('marketplace.priceOnRequest'))}
                </p>
                {product.description ? <p className="prewrap">{product.description}</p> : null}
              </SectionCard>
              <SectionCard title={t('marketplace.supplier')} headingLevel={2}>
                <p>
                  <strong>{product.company.name}</strong>
                </p>
                <p className="text-caption">
                  {name(product.company.governorate)}
                  {product.company.city ? ` · ${name(product.company.city)}` : ''}
                </p>
                {product.company.phone ? <p dir="ltr">{product.company.phone}</p> : null}
                {product.company.public_email ? <p dir="ltr">{product.company.public_email}</p> : null}
                {product.company.website ? (
                  <a href={product.company.website} target="_blank" rel="noopener noreferrer" dir="ltr">
                    {product.company.website}
                  </a>
                ) : null}
              </SectionCard>
              {product.can_buy_directly ? <DirectPurchase product={product} /> : null}
              <SectionCard title={t('quotes.request')} description={t('quotes.intro')} headingLevel={2}>
                <RequestQuoteForm productId={product.id} variants={product.variants ?? []} />
              </SectionCard>
            </PageStack>
          </>
        )}
      </AsyncPage>
    </Container>
  )
}

/** Verified professionals may order a priced B2B_VERIFIED_ONLY product without a quotation
 * (the server re-checks targeting, compliance, price and stock at checkout). */
function DirectPurchase({ product }: { product: MarketplaceProduct }) {
  const { t } = useTranslation()
  const variants = product.variants ?? []
  const [variantId, setVariantId] = useState(variants[0]?.id ?? '')
  const [qty, setQty] = useState(1)
  const [added, setAdded] = useState(false)
  const variant = variants.find((v) => v.id === variantId)
  return (
    <SectionCard title={t('marketplace.buyNow')} description={t('marketplace.buyNowIntro')} headingLevel={2}>
      <div className="cluster" style={{ alignItems: 'flex-end' }} data-testid="direct-purchase">
        {variants.length ? (
          <Select label={t('store.chooseOption')} value={variantId} onChange={(e) => setVariantId(e.target.value)}>
            {variants.map((v) => (
              <option key={v.id} value={v.id} disabled={!v.in_stock}>{v.label}</option>
            ))}
          </Select>
        ) : null}
        <QuantityStepper value={qty} onChange={setQty} />
        <Button
          leading={<Icon name="cart" size={16} />}
          onClick={() => {
            cart.add(
              {
                product: product.id,
                ...(variant ? { variant: variant.id, variantLabel: variant.label } : {}),
                title: product.title,
                price: variant?.price ?? product.price ?? '0',
                currency: product.currency,
                merchantId: product.company.id,
                merchantName: product.company.name,
                image: product.images?.[0]?.url || product.image_url || '',
                source: 'B2B',
              },
              qty,
            )
            setAdded(true)
          }}
        >
          {t('store.addToCart')}
        </Button>
      </div>
      {added ? (
        <Alert kind="success">
          <Link to="/cart">{t('store.goToCart')}</Link>
        </Alert>
      ) : null}
    </SectionCard>
  )
}
