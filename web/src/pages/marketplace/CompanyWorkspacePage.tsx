import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { ApiError, marketplace as marketplaceApi, reference } from '../../api'
import type { CompanyProduct, Governorate, MedicalCompany, ProductCategory } from '../../api'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Badge,
  Button,
  Container,
  EmptyState,
  ErrorState,
  FormActions,
  Icon,
  LoadingState,
  PageHeader,
  PageStack,
  Pagination,
  SectionCard,
  Select,
  StatCard,
  Textarea,
  TextField,
  useFormErrors,
} from '../../design-system'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { ClientValidationError } from '../validation'
import { formatProductPrice } from './MarketplacePage'

const PAGE_SIZE = 20
const REQUESTABLE = ['UNVERIFIED', 'REJECTED']

type Loaded = [MedicalCompany | null, Governorate[], ProductCategory[]]

/** /company — medical company onboarding, verification, dashboard and products. */
export function CompanyWorkspacePage() {
  const { t } = useTranslation()
  const load = async (signal: AbortSignal): Promise<Loaded> => {
    const company = await marketplaceApi.getMyCompany(signal).catch((e: unknown) => {
      if (e instanceof ApiError && e.status === 404) return null
      throw e
    })
    const [governorates, categories] = await Promise.all([
      reference.listGovernorates(undefined, signal),
      marketplaceApi.listCategories(signal),
    ])
    return [company, governorates, categories]
  }
  return (
    <Container width="xl">
      <AsyncPage load={load}>
        {([company, governorates, categories], reload) =>
          company ? (
            <Workspace company={company} governorates={governorates} categories={categories} reload={reload} />
          ) : (
            <Container width="md" style={{ paddingInline: 0 }}>
              <PageHeader
                eyebrow={<><Icon name="cart" size={16} />{t('modules.marketplace')}</>}
                title={t('company.onboardingTitle')}
                description={t('company.onboardingIntro')}
              />
              <div className="card-block" data-testid="company-onboarding">
                <CompanyForm company={null} governorates={governorates} onSaved={reload} />
              </div>
            </Container>
          )
        }
      </AsyncPage>
    </Container>
  )
}

function Workspace({ company, governorates, categories, reload }: { company: MedicalCompany; governorates: Governorate[]; categories: ProductCategory[]; reload: () => void }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const dashboard = useAsyncData((signal) => marketplaceApi.getCompanyDashboard(signal), [])
  const products = useAsyncData((signal) => marketplaceApi.listMyProducts(page, signal), [page])
  const [editing, setEditing] = useState<CompanyProduct | null>(null)
  const [error, setError] = useState<string | null>(null)
  const refresh = () => {
    dashboard.reload()
    products.reload()
  }
  const statusTone = company.verification_status === 'VERIFIED' ? 'success' : company.verification_status === 'PENDING' ? 'warning' : company.verification_status === 'UNVERIFIED' ? 'neutral' : 'error'

  return (
    <>
      <PageHeader
        eyebrow={<><Icon name="cart" size={16} />{t('modules.marketplace')}</>}
        title={company.name}
        description={t('company.intro')}
        actions={<Badge tone={statusTone}>{t(`verification.${company.verification_status}`)}</Badge>}
      />
      <PageStack>
        <SectionCard title={t('company.dashboard')} headingLevel={2}>
          {dashboard.loading ? (
            <LoadingState testId="company-dashboard-loading" />
          ) : dashboard.error ? (
            <ErrorState error={dashboard.error} onRetry={dashboard.reload} />
          ) : dashboard.data ? (
            <div className="grid-2" data-testid="company-dashboard">
              <StatCard label={t('company.productsTotal')} value={<span data-testid="stat-total">{dashboard.data.products_total}</span>} />
              <StatCard label={t('company.productsActive')} value={<span data-testid="stat-active">{dashboard.data.products_active}</span>} />
              <StatCard label={t('company.productsInactive')} value={<span data-testid="stat-inactive">{dashboard.data.products_inactive}</span>} />
              <StatCard label={t('company.productsExposable')} value={<span data-testid="stat-exposable">{dashboard.data.products_exposable}</span>} hint={t('company.exposableHint')} />
            </div>
          ) : null}
        </SectionCard>

        <VerificationBlock company={company} onChange={reload} />

        <SectionCard title={editing ? t('company.editProduct') : t('company.newProduct')} headingLevel={2}>
          {categories.length === 0 ? (
            <EmptyState icon="tag" title={t('company.noCategories')} testId="company-no-categories" />
          ) : (
            <ProductForm
              key={editing?.id ?? 'new'}
              product={editing}
              categories={categories}
              onSaved={() => {
                setEditing(null)
                refresh()
              }}
              onCancel={editing ? () => setEditing(null) : undefined}
            />
          )}
        </SectionCard>

        <SectionCard title={t('company.myProducts')} description={company.can_publish ? undefined : t('company.cannotPublish')} headingLevel={2}>
          {error ? <Alert kind="error">{error}</Alert> : null}
          {products.loading ? (
            <LoadingState testId="company-products-loading" />
          ) : products.error ? (
            <ErrorState error={products.error} onRetry={products.reload} />
          ) : (products.data?.results ?? []).length === 0 ? (
            <EmptyState icon="cart" title={t('company.noProducts')} testId="company-products-empty" />
          ) : (
            <ul className="stack">
              {(products.data?.results ?? []).map((product) => (
                <li key={product.id} className="card-block" data-testid="company-product">
                  <div className="cluster">
                    <strong>{product.title}</strong>
                    <Badge tone="outline">{name(product.category)}</Badge>
                    <Badge tone={product.is_active ? 'success' : 'neutral'}>{product.is_active ? t('company.active') : t('company.inactive')}</Badge>
                  </div>
                  <div className="text-caption" dir="auto">{formatProductPrice(product, i18n.language, t('marketplace.priceOnRequest'))}</div>
                  <div className="cluster" style={{ marginBlockStart: 'var(--space-2)' }}>
                    <Button variant="ghost" size="sm" onClick={() => setEditing(product)} leading={<Icon name="edit" size={16} />}>
                      {t('company.edit')}
                    </Button>
                    {product.is_active ? (
                      <ApiActionButton size="sm" variant="secondary" action={() => marketplaceApi.setMyProductActive(product.id, false)} onSuccess={() => { setError(null); refresh() }} onError={(e) => setError(toErrorMessage(e))}>
                        {t('company.deactivate')}
                      </ApiActionButton>
                    ) : company.can_publish ? (
                      // The backend refuses publication for a company that is not verified: no button then.
                      <ApiActionButton size="sm" action={() => marketplaceApi.setMyProductActive(product.id, true)} onSuccess={() => { setError(null); refresh() }} onError={(e) => setError(toErrorMessage(e))}>
                        {t('company.activate')}
                      </ApiActionButton>
                    ) : null}
                  </div>
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
              onChange={(next) => setParams(next > 1 ? { page: String(next) } : {})}
            />
          ) : null}
        </SectionCard>

        <SectionCard title={t('company.profile')} headingLevel={2}>
          <CompanyForm company={company} governorates={governorates} onSaved={reload} />
        </SectionCard>
      </PageStack>
    </>
  )
}

function VerificationBlock({ company, onChange }: { company: MedicalCompany; onChange: () => void }) {
  const { t } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  return (
    <SectionCard title={t('company.verification')} headingLevel={2}>
      <p className="text-secondary" data-testid="company-verification-state">
        {t(`company.verificationState.${company.verification_status}`)}
      </p>
      {company.verification_note ? <Alert kind="info">{company.verification_note}</Alert> : null}
      {error ? <Alert kind="error">{error}</Alert> : null}
      {REQUESTABLE.includes(company.verification_status) ? (
        <ApiActionButton action={() => marketplaceApi.requestCompanyVerification()} onSuccess={() => { setError(null); onChange() }} onError={(e) => setError(toErrorMessage(e))} pendingLabel={t('company.requesting')} leading={<Icon name="shieldCheck" size={18} />}>
          {t('company.requestVerification')}
        </ApiActionButton>
      ) : null}
    </SectionCard>
  )
}

function CompanyForm({ company, governorates, onSaved }: { company: MedicalCompany | null; governorates: Governorate[]; onSaved: () => void }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const [f, setF] = useState({
    name: company?.name ?? '',
    description: company?.description ?? '',
    phone: company?.phone ?? '',
    public_email: company?.public_email ?? '',
    website: company?.website ?? '',
    governorate: company?.governorate.id ?? '',
    address: company?.address ?? '',
  })
  const errors = useFormErrors(['name', 'description', 'phone', 'public_email', 'website', 'governorate', 'address'] as const)
  const set = (key: keyof typeof f, value: string) => setF((prev) => ({ ...prev, [key]: value }))
  // Backend rule (identity_locked): what the administrator reviews is frozen while review is pending or granted.
  const identityLocked = company?.identity_locked === true
  const submit = async () => {
    const next: Record<string, string> = {}
    if (!f.name.trim()) next.name = t('validation.required')
    if (!f.governorate) next.governorate = t('validation.required')
    if (Object.keys(next).length) {
      errors.setFieldErrors(next)
      throw new ClientValidationError()
    }
    const editable = { description: f.description.trim(), phone: f.phone, public_email: f.public_email }
    const payload = identityLocked
      ? editable
      : { ...editable, name: f.name.trim(), governorate: f.governorate, address: f.address.trim(), website: f.website }
    return company ? marketplaceApi.updateMyCompany(payload) : marketplaceApi.createMyCompany(payload)
  }
  return (
    <form noValidate onSubmit={(e) => e.preventDefault()}>
      {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
      {identityLocked ? <Alert kind="info">{t('company.identityLocked')}</Alert> : null}
      <TextField label={t('company.name')} value={f.name} onChange={(e) => set('name', e.target.value)} error={errors.fieldErrors.name} required disabled={identityLocked} />
      <Textarea label={t('company.description')} optional rows={3} value={f.description} onChange={(e) => set('description', e.target.value)} error={errors.fieldErrors.description} />
      <div className="grid-2">
        <Select label={t('company.governorate')} value={f.governorate} onChange={(e) => set('governorate', e.target.value)} error={errors.fieldErrors.governorate} required disabled={identityLocked}>
          <option value="">{t('company.chooseGovernorate')}</option>
          {governorates.map((g) => (
            <option key={g.id} value={g.id}>
              {name(g)}
            </option>
          ))}
        </Select>
        <TextField label={t('company.address')} optional value={f.address} onChange={(e) => set('address', e.target.value)} error={errors.fieldErrors.address} disabled={identityLocked} />
      </div>
      <div className="grid-2">
        <TextField label={t('company.phone')} optional dir="ltr" value={f.phone} onChange={(e) => set('phone', e.target.value)} error={errors.fieldErrors.phone} />
        <TextField label={t('company.email')} optional dir="ltr" type="email" value={f.public_email} onChange={(e) => set('public_email', e.target.value)} error={errors.fieldErrors.public_email} />
      </div>
      <TextField label={t('company.website')} optional dir="ltr" value={f.website} onChange={(e) => set('website', e.target.value)} error={errors.fieldErrors.website} disabled={identityLocked} />
      <FormActions>
        <ApiActionButton type="submit" action={submit} onSuccess={() => onSaved()} onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }} pendingLabel={t('common.saving')}>
          {company ? t('company.save') : t('company.create')}
        </ApiActionButton>
      </FormActions>
    </form>
  )
}

function ProductForm({ product, categories, onSaved, onCancel }: { product: CompanyProduct | null; categories: ProductCategory[]; onSaved: () => void; onCancel?: () => void }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const [f, setF] = useState({
    category: product?.category.id ?? '',
    title: product?.title ?? '',
    description: product?.description ?? '',
    brand: product?.brand ?? '',
    model_name: product?.model_name ?? '',
    price: product?.price ?? '',
    currency: product?.currency ?? 'IQD',
  })
  const errors = useFormErrors(['category', 'title', 'description', 'brand', 'model_name', 'price', 'currency'] as const)
  const set = (key: keyof typeof f, value: string) => setF((prev) => ({ ...prev, [key]: value }))
  const submit = async () => {
    const next: Record<string, string> = {}
    if (!f.category) next.category = t('validation.required')
    if (!f.title.trim()) next.title = t('validation.required')
    if (f.price !== '' && (Number.isNaN(Number(f.price)) || Number(f.price) < 0)) next.price = t('company.invalidPrice')
    if (Object.keys(next).length) {
      errors.setFieldErrors(next)
      throw new ClientValidationError()
    }
    const payload = {
      category: f.category,
      title: f.title.trim(),
      description: f.description.trim(),
      brand: f.brand.trim(),
      model_name: f.model_name.trim(),
      price: f.price === '' ? null : f.price,
      currency: f.currency,
    }
    return product ? marketplaceApi.updateMyProduct(product.id, payload) : marketplaceApi.createMyProduct(payload)
  }
  return (
    <form noValidate onSubmit={(e) => e.preventDefault()} data-testid="product-form">
      {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
      <p className="text-caption">{t('company.targetingNote')}</p>
      <div className="grid-2">
        <Select label={t('marketplace.category')} value={f.category} onChange={(e) => set('category', e.target.value)} error={errors.fieldErrors.category} required>
          <option value="">{t('company.chooseCategory')}</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {name(c)}
            </option>
          ))}
        </Select>
        <TextField label={t('company.productTitle')} value={f.title} onChange={(e) => set('title', e.target.value)} error={errors.fieldErrors.title} required />
      </div>
      <Textarea label={t('company.description')} optional rows={3} value={f.description} onChange={(e) => set('description', e.target.value)} error={errors.fieldErrors.description} />
      <div className="grid-2">
        <TextField label={t('company.brand')} optional value={f.brand} onChange={(e) => set('brand', e.target.value)} error={errors.fieldErrors.brand} />
        <TextField label={t('company.model')} optional value={f.model_name} onChange={(e) => set('model_name', e.target.value)} error={errors.fieldErrors.model_name} />
      </div>
      <div className="grid-2">
        <TextField label={t('marketplace.price')} optional hint={t('company.priceHint')} dir="ltr" inputMode="decimal" value={f.price} onChange={(e) => set('price', e.target.value)} error={errors.fieldErrors.price} />
        <Select label={t('company.currency')} value={f.currency} onChange={(e) => set('currency', e.target.value)} error={errors.fieldErrors.currency}>
          <option value="IQD">IQD</option>
          <option value="USD">USD</option>
        </Select>
      </div>
      <FormActions>
        {onCancel ? (
          <Button variant="ghost" onClick={onCancel}>
            {t('company.cancel')}
          </Button>
        ) : null}
        <ApiActionButton type="submit" action={submit} onSuccess={() => onSaved()} onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }} pendingLabel={t('common.saving')}>
          {product ? t('company.saveProduct') : t('company.createProduct')}
        </ApiActionButton>
      </FormActions>
    </form>
  )
}
