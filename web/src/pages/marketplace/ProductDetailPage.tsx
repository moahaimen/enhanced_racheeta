import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'

import { ApiError, marketplace as marketplaceApi } from '../../api'
import { AsyncPage, Badge, Container, Icon, PageHeader, PageStack, SectionCard } from '../../design-system'
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
            </PageStack>
          </>
        )}
      </AsyncPage>
    </Container>
  )
}
