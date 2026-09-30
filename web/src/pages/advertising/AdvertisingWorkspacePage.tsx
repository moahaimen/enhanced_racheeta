import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { ApiError, PROVIDER_TYPES, advertising as advertisingApi, marketplace as marketplaceApi, reference } from '../../api'
import type { Campaign, CampaignStatus, CampaignWrite, CompanyProduct, Governorate, MedicalCompany, ProviderType, Specialty } from '../../api'
import type { BadgeTone } from '../../design-system'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Badge,
  Button,
  Checkbox,
  CheckboxGroup,
  Container,
  EmptyState,
  ErrorState,
  FormActions,
  Icon,
  LinkButton,
  LoadingState,
  PageHeader,
  PageStack,
  Pagination,
  SectionCard,
  Select,
  StatCard,
  TextField,
  useFormErrors,
} from '../../design-system'
import { useAsyncData } from '../../hooks/useAsync'
import { useLocalizedName } from '../../i18n/localized'
import { ClientValidationError } from '../validation'
import { formatMoney, isDateRange, refusalMessage } from './advertisingFormat'
import { TargetingSummary } from './TargetingSummary'

const PAGE_SIZE = 20

async function loadAllMyProducts(signal: AbortSignal): Promise<CompanyProduct[]> {
  const out: CompanyProduct[] = []
  for (let page = 1; page <= 10; page++) {
    const res = await marketplaceApi.listMyProducts(page, signal)
    out.push(...res.results)
    if (!res.next) break
  }
  return out
}

type Loaded = [MedicalCompany | null, CompanyProduct[], Governorate[], Specialty[]]

const STATUS_TONE: Record<CampaignStatus, BadgeTone> = {
  DRAFT: 'neutral',
  PENDING_PAYMENT: 'warning',
  ACTIVE: 'success',
  REJECTED: 'error',
  CANCELLED: 'neutral',
}

/** /company/advertising — sponsored-product campaigns of a medical company. Price, payment and status are the backend's. */
export function AdvertisingWorkspacePage() {
  const { t } = useTranslation()
  const load = async (signal: AbortSignal): Promise<Loaded> => {
    const company = await marketplaceApi.getMyCompany(signal).catch((e: unknown) => {
      if (e instanceof ApiError && e.status === 404) return null
      throw e
    })
    if (!company) return [null, [], [], []]
    const [products, governorates, specialties] = await Promise.all([loadAllMyProducts(signal), reference.listGovernorates(undefined, signal), reference.listSpecialties(signal)])
    return [company, products, governorates, specialties]
  }
  return (
    <Container width="xl">
      <AsyncPage load={load}>
        {([company, products, governorates, specialties]) =>
          company ? (
            <Workspace products={products} governorates={governorates} specialties={specialties} />
          ) : (
            <EmptyState
              icon="cart"
              title={t('advertising.needCompany')}
              testId="advertising-no-company"
              action={<LinkButton to="/company">{t('company.open')}</LinkButton>}
            />
          )
        }
      </AsyncPage>
    </Container>
  )
}

function Workspace({ products, governorates, specialties }: { products: CompanyProduct[]; governorates: Governorate[]; specialties: Specialty[] }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const dashboard = useAsyncData((signal) => advertisingApi.getCampaignDashboard(signal), [])
  const campaigns = useAsyncData((signal) => advertisingApi.listMyCampaigns(page, signal), [page])
  const [editing, setEditing] = useState<Campaign | null>(null)
  const [error, setError] = useState<string | null>(null)
  const refresh = () => {
    dashboard.reload()
    campaigns.reload()
  }
  const done = () => {
    setError(null)
    refresh()
  }
  const fail = (e: unknown) => setError(refusalMessage(e, t))

  return (
    <>
      <PageHeader
        eyebrow={<><Icon name="tag" size={16} />{t('modules.marketplace')}</>}
        title={t('advertising.title')}
        description={t('advertising.intro')}
        actions={
          <LinkButton to="/company" variant="ghost" size="sm">
            {t('advertising.backToCompany')}
          </LinkButton>
        }
      />
      <PageStack>
        <SectionCard title={t('advertising.dashboard')} headingLevel={2}>
          {dashboard.loading ? (
            <LoadingState testId="advertising-dashboard-loading" />
          ) : dashboard.error ? (
            <ErrorState error={dashboard.error} onRetry={dashboard.reload} />
          ) : dashboard.data ? (
            <div className="grid-2" data-testid="advertising-dashboard">
              <StatCard label={t('advertising.stats.total')} value={<span data-testid="stat-total">{dashboard.data.campaigns_total}</span>} />
              <StatCard label={t('advertising.stats.draft')} value={<span data-testid="stat-draft">{dashboard.data.campaigns_draft}</span>} />
              <StatCard label={t('advertising.stats.pending')} value={<span data-testid="stat-pending">{dashboard.data.campaigns_pending_payment}</span>} />
              <StatCard label={t('advertising.stats.active')} value={<span data-testid="stat-active">{dashboard.data.campaigns_active}</span>} />
              <StatCard label={t('advertising.stats.live')} value={<span data-testid="stat-live">{dashboard.data.campaigns_live}</span>} hint={t('advertising.stats.liveHint')} />
              <StatCard label={t('advertising.stats.ended')} value={<span data-testid="stat-ended">{dashboard.data.campaigns_ended}</span>} />
              <StatCard label={t('advertising.stats.rejected')} value={<span data-testid="stat-rejected">{dashboard.data.campaigns_rejected}</span>} />
              <StatCard label={t('advertising.stats.cancelled')} value={<span data-testid="stat-cancelled">{dashboard.data.campaigns_cancelled}</span>} />
            </div>
          ) : null}
        </SectionCard>

        <SectionCard title={editing ? t('advertising.editCampaign') : t('advertising.newCampaign')} headingLevel={2}>
          {products.length === 0 && !editing ? (
            <EmptyState icon="cart" title={t('advertising.noProducts')} testId="advertising-no-products" action={<LinkButton to="/company">{t('company.open')}</LinkButton>} />
          ) : (
            <CampaignForm
              key={editing?.id ?? 'new'}
              campaign={editing}
              products={products}
              governorates={governorates}
              specialties={specialties}
              onSaved={() => {
                setEditing(null)
                done()
              }}
              onCancel={editing ? () => setEditing(null) : undefined}
            />
          )}
        </SectionCard>

        <SectionCard title={t('advertising.myCampaigns')} headingLevel={2}>
          {error ? <Alert kind="error">{error}</Alert> : null}
          {campaigns.loading ? (
            <LoadingState testId="advertising-campaigns-loading" />
          ) : campaigns.error ? (
            <ErrorState error={campaigns.error} onRetry={campaigns.reload} />
          ) : (campaigns.data?.results ?? []).length === 0 ? (
            <EmptyState icon="tag" title={t('advertising.noCampaigns')} testId="advertising-campaigns-empty" />
          ) : (
            <ul className="stack" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {(campaigns.data?.results ?? []).map((c) => (
                <li key={c.id} className="card-block" data-testid="campaign">
                  <div className="cluster">
                    <strong>{c.name}</strong>
                    <Badge tone={STATUS_TONE[c.status]}>{t(`campaignStatus.${c.status}`)}</Badge>
                    {c.is_live ? <Badge tone="brand">{t('advertising.live')}</Badge> : null}
                    {c.is_ended ? <Badge tone="warning">{t('advertising.ended')}</Badge> : null}
                  </div>
                  <div className="text-caption">
                    {c.product.title} · {name(c.product.category)}
                    {!c.product.is_active ? ` · ${t('advertising.productInactive')}` : ''}
                  </div>
                  <div className="text-caption" dir="auto">
                    {c.starts_on && c.ends_on ? `${c.starts_on} → ${c.ends_on}` : t('advertising.noDates')}
                  </div>
                  <TargetingSummary campaign={c} />
                  {c.quote ? (
                    <div className="text-secondary" dir="auto" data-testid="campaign-quote">
                      {t('advertising.quotedLine', { days: c.quote.days, rate: formatMoney(c.quote.daily_rate, c.quote.currency, i18n.language), amount: formatMoney(c.quote.amount, c.quote.currency, i18n.language) })}
                    </div>
                  ) : null}
                  {c.payment ? (
                    <div className="text-caption" data-testid="campaign-payment">
                      {t('advertising.paymentLine', { status: t(`paymentStatus.${c.payment.status}`) })}
                      {c.payment.method ? ` · ${t(`paymentMethods.${c.payment.method}`)}` : ''}
                      {c.payment.reference ? ` · ${c.payment.reference}` : ''}
                    </div>
                  ) : null}
                  {c.status === 'PENDING_PAYMENT' ? (
                    <Alert kind="info">
                      <strong data-testid="pending-title">{t('advertising.pendingTitle')}</strong> {t('advertising.pendingBody')}
                    </Alert>
                  ) : null}
                  {c.status === 'REJECTED' ? <Alert kind="error">{t('advertising.rejectedBody')}</Alert> : null}
                  {c.status === 'CANCELLED' ? <p className="text-caption">{t('advertising.cancelledBody')}</p> : null}
                  {c.is_ended ? <p className="text-caption">{t('advertising.endedBody')}</p> : null}
                  <div className="cluster" style={{ marginBlockStart: 'var(--space-2)' }}>
                    {c.status === 'DRAFT' ? (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => setEditing(c)} leading={<Icon name="edit" size={16} />}>
                          {t('advertising.edit')}
                        </Button>
                        {!c.starts_on || !c.ends_on ? (
                          <span className="text-caption" data-testid="submit-hint">{t('advertising.needDates')}</span>
                        ) : !c.product.is_active ? (
                          <span className="text-caption" data-testid="submit-hint">{t('advertising.publishProductFirst')}</span>
                        ) : (
                          // Guidance only: the backend prices, checks eligibility and creates the payment record.
                          <ApiActionButton size="sm" action={() => advertisingApi.submitCampaign(c.id)} onSuccess={done} onError={fail} pendingLabel={t('advertising.submitting')}>
                            {t('advertising.submit')}
                          </ApiActionButton>
                        )}
                      </>
                    ) : null}
                    {c.status === 'ACTIVE' ? (
                      <ApiActionButton size="sm" variant="danger" action={() => advertisingApi.cancelCampaign(c.id)} onSuccess={done} onError={fail} pendingLabel={t('advertising.cancelling')}>
                        {t('advertising.cancelCampaign')}
                      </ApiActionButton>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
          {campaigns.data ? (
            <Pagination
              page={page}
              total={Math.max(1, Math.ceil(campaigns.data.count / PAGE_SIZE))}
              hasNext={campaigns.data.next !== null}
              hasPrevious={campaigns.data.previous !== null}
              onChange={(next) => setParams(next > 1 ? { page: String(next) } : {})}
            />
          ) : null}
        </SectionCard>
      </PageStack>
    </>
  )
}

/** The backend's CURRENT price for the chosen dates. A preview: submission recalculates it and the browser never sends it back. */
function QuotePreview({ starts, ends }: { starts: string; ends: string }) {
  const { t, i18n } = useTranslation()
  const quote = useAsyncData((signal) => advertisingApi.quoteCampaign({ starts_on: starts, ends_on: ends }, signal), [starts, ends])
  return (
    <div className="card-block" data-testid="quote-preview" aria-live="polite">
      <strong>{t('advertising.quote.title')}</strong>
      {quote.loading ? (
        <LoadingState testId="quote-loading" />
      ) : quote.error ? (
        quote.error instanceof ApiError && quote.error.code === 'pricing_unavailable' ? (
          <Alert kind="warning">
            <span data-testid="pricing-unavailable">{t('advertising.pricingUnavailable')}</span>
          </Alert>
        ) : (
          <ErrorState error={quote.error} onRetry={quote.reload} />
        )
      ) : quote.data ? (
        <dl className="cluster" style={{ margin: 0 }}>
          <div>
            <dt className="text-caption">{t('advertising.quote.dailyRate')}</dt>
            <dd data-testid="quote-rate" dir="auto">{formatMoney(quote.data.daily_rate, quote.data.currency, i18n.language)}</dd>
          </div>
          <div>
            <dt className="text-caption">{t('advertising.quote.days')}</dt>
            <dd data-testid="quote-days">{quote.data.days}</dd>
          </div>
          <div>
            <dt className="text-caption">{t('advertising.quote.total')}</dt>
            <dd data-testid="quote-total" dir="auto">{formatMoney(quote.data.total, quote.data.currency, i18n.language)}</dd>
          </div>
        </dl>
      ) : null}
      <p className="text-caption">{t('advertising.quote.note')}</p>
    </div>
  )
}

const FIELDS = ['name', 'product', 'starts_on', 'ends_on', 'provider_types', 'specialties', 'governorates'] as const

function CampaignForm({
  campaign,
  products,
  governorates,
  specialties,
  onSaved,
  onCancel,
}: {
  campaign: Campaign | null
  products: CompanyProduct[]
  governorates: Governorate[]
  specialties: Specialty[]
  onSaved: () => void
  onCancel?: () => void
}) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const [f, setF] = useState({
    name: campaign?.name ?? '',
    product: campaign?.product.id ?? '',
    starts_on: campaign?.starts_on ?? '',
    ends_on: campaign?.ends_on ?? '',
    provider_types: (campaign?.provider_types ?? []) as ProviderType[],
    specialties: (campaign?.specialties.map((s) => s.id) ?? []) as string[],
    governorates: (campaign?.governorates.map((g) => g.id) ?? []) as string[],
  })
  const errors = useFormErrors(FIELDS)
  const set = <K extends keyof typeof f>(key: K, value: (typeof f)[K]) => setF((prev) => ({ ...prev, [key]: value }))
  const toggle = <T,>(key: 'provider_types' | 'specialties' | 'governorates', value: T) =>
    setF((prev) => {
      const list = prev[key] as unknown as T[]
      return { ...prev, [key]: list.includes(value) ? list.filter((v) => v !== value) : [...list, value] }
    })

  // A saved target that is no longer in the ACTIVE reference lists stays visible (checked, labelled) so it can be
  // unchecked — otherwise a campaign could never be fixed. It is never offered as a new choice.
  const activeGovernorateIds = new Set(governorates.map((g) => g.id))
  const activeSpecialtyIds = new Set(specialties.map((s) => s.id))
  const staleGovernorates = (campaign?.governorates ?? []).filter((g) => !activeGovernorateIds.has(g.id))
  const staleSpecialties = (campaign?.specialties ?? []).filter((s) => !activeSpecialtyIds.has(s.id))
  const productChoices = campaign && !products.some((p) => p.id === campaign.product.id) ? [{ id: campaign.product.id, title: campaign.product.title, is_active: campaign.product.is_active }, ...products] : products
  const range = isDateRange(f.starts_on, f.ends_on)

  const submit = async () => {
    const next: Record<string, string> = {}
    if (!f.name.trim()) next.name = t('validation.required')
    if (!f.product) next.product = t('validation.required')
    if (f.starts_on && f.ends_on && f.ends_on < f.starts_on) next.ends_on = t('advertising.datesInvalid')
    if (Object.keys(next).length) {
      errors.setFieldErrors(next)
      throw new ClientValidationError()
    }
    // Only owner-editable data: no price, payment, status or company ever leaves the browser.
    const payload: CampaignWrite = {
      name: f.name.trim(),
      product: f.product,
      starts_on: f.starts_on || null,
      ends_on: f.ends_on || null,
      provider_types: f.provider_types,
      specialties: f.specialties,
      governorates: f.governorates,
    }
    return campaign ? advertisingApi.updateCampaign(campaign.id, payload) : advertisingApi.createCampaign(payload)
  }

  return (
    <form noValidate onSubmit={(e) => e.preventDefault()} data-testid="campaign-form">
      {errors.formError ? <Alert kind="error">{errors.formError}</Alert> : null}
      <p className="text-caption">{t('advertising.targetingNote')}</p>
      <div className="grid-2">
        <TextField label={t('advertising.name')} hint={t('advertising.nameHint')} value={f.name} onChange={(e) => set('name', e.target.value)} error={errors.fieldErrors.name} required />
        <Select label={t('advertising.product')} value={f.product} onChange={(e) => set('product', e.target.value)} error={errors.fieldErrors.product} required>
          <option value="">{t('advertising.chooseProduct')}</option>
          {productChoices.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
              {!p.is_active ? ` (${t('advertising.productInactive')})` : ''}
            </option>
          ))}
        </Select>
      </div>
      <div className="grid-2">
        <TextField label={t('advertising.startsOn')} type="date" dir="ltr" value={f.starts_on} onChange={(e) => set('starts_on', e.target.value)} error={errors.fieldErrors.starts_on} />
        <TextField label={t('advertising.endsOn')} type="date" dir="ltr" value={f.ends_on} onChange={(e) => set('ends_on', e.target.value)} error={errors.fieldErrors.ends_on} />
      </div>
      {range ? <QuotePreview starts={f.starts_on} ends={f.ends_on} /> : <p className="text-caption">{t('advertising.quote.needDates')}</p>}
      <CheckboxGroup legend={t('advertising.providerTypes')} error={errors.fieldErrors.provider_types}>
        {PROVIDER_TYPES.map((type) => (
          <Checkbox key={type} label={t(`providerTypes.${type}`)} checked={f.provider_types.includes(type)} onChange={() => toggle('provider_types', type)} />
        ))}
      </CheckboxGroup>
      <CheckboxGroup legend={t('advertising.specialties')} error={errors.fieldErrors.specialties}>
        {[...specialties.map((s) => ({ s, stale: false })), ...staleSpecialties.map((s) => ({ s, stale: true }))].map(({ s, stale }) => (
          <Checkbox key={s.id} label={stale ? t('advertising.currentUnavailable', { name: name(s) }) : name(s)} checked={f.specialties.includes(s.id)} onChange={() => toggle('specialties', s.id)} />
        ))}
      </CheckboxGroup>
      <CheckboxGroup legend={t('advertising.governorates')} error={errors.fieldErrors.governorates}>
        {[...governorates.map((g) => ({ g, stale: false })), ...staleGovernorates.map((g) => ({ g, stale: true }))].map(({ g, stale }) => (
          <Checkbox key={g.id} label={stale ? t('advertising.currentUnavailable', { name: name(g) }) : name(g)} checked={f.governorates.includes(g.id)} onChange={() => toggle('governorates', g.id)} />
        ))}
      </CheckboxGroup>
      <FormActions>
        {onCancel ? (
          <Button variant="ghost" onClick={onCancel}>
            {t('advertising.cancel')}
          </Button>
        ) : null}
        <ApiActionButton type="submit" action={submit} onSuccess={() => onSaved()} onError={(e) => { if (!(e instanceof ClientValidationError)) errors.applyApiError(e) }} pendingLabel={t('common.saving')}>
          {campaign ? t('advertising.saveDraft') : t('advertising.createDraft')}
        </ApiActionButton>
      </FormActions>
    </form>
  )
}

