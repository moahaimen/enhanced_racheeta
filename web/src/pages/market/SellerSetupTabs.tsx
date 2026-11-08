import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { commerce, marketplace as mp, reference } from '../../api'
import type {
  CompanyProduct,
  Governorate,
  MedicalCompany,
  OwnerVariant,
  ProductPhoto,
  SellerDocument,
  SellerDocumentKind,
  TaxMode,
} from '../../api'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Badge,
  Button,
  EmptyState,
  Icon,
  SectionCard,
  Select,
  StatCard,
  TextField,
} from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import { pickScript, useLocalizedName } from '../../i18n/localized'
import { downloadBlob } from './files'
import { useMoney } from './money'

const DOCUMENT_KINDS: SellerDocumentKind[] = [
  'COMMERCIAL_REGISTRATION',
  'PHARMACY_LICENSE',
  'MOH_IMPORT_LICENSE',
  'SCIENTIFIC_OFFICE_LICENSE',
  'DEVICE_REGISTRATION',
  'OWNER_ID',
  'OTHER',
]
const DOC_TONE = { PENDING: 'warning', APPROVED: 'success', REJECTED: 'error' } as const
const STORE_TONE = { ACTIVE: 'success', PAUSED: 'warning', INACTIVE: 'neutral' } as const

function useErrors() {
  const [error, setError] = useState<string | null>(null)
  return { error, fail: (e: unknown) => setError(toErrorMessage(e)), clear: () => setError(null) }
}

/** Opens a private file (document or photo) with the caller's credentials, in a new tab. */
async function openPrivate(url: string, company?: string) {
  const blob = await mp.fetchPrivateFile(url, company)
  const href = URL.createObjectURL(blob)
  window.open(href, '_blank', 'noopener,noreferrer')
  window.setTimeout(() => URL.revokeObjectURL(href), 60_000)
}

/** A product photo loaded with the seller's credentials (unpublished photos are private). */
function PrivatePhoto({ photo, company }: { photo: ProductPhoto; company?: string }) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    let href: string | null = null
    let alive = true
    mp.fetchPrivateFile(photo.url, company)
      .then((blob) => {
        if (!alive) return
        href = URL.createObjectURL(blob)
        setSrc(href)
      })
      .catch(() => setSrc(null))
    return () => {
      alive = false
      if (href) URL.revokeObjectURL(href)
    }
  }, [photo.url, company])
  return src ? <img src={src} alt={photo.alt_text} width={64} height={64} style={{ objectFit: 'cover', borderRadius: 'var(--radius-sm)' }} /> : <span className="text-caption">…</span>
}

// ---- store setup: verification, documents, activation -----------------------------------------------
export function SetupTab({ company }: { company?: string }) {
  const { t } = useTranslation()
  const { error, fail, clear } = useErrors()
  return (
    <>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <AsyncPage
        load={async (signal) => {
          const [store, documents] = await Promise.all([mp.getStore(company, signal), mp.listDocuments(company, signal)])
          return { store, documents }
        }}
        deps={[company]}
      >
        {({ store, documents }, reload) => (
          <>
            <StoreStatusCard store={store} company={company} onDone={() => { clear(); reload() }} onError={fail} />
            <SectionCard headingLevel={2} title={t('sellerSetup.documents')} description={t('sellerSetup.documentsIntro')}>
              <RequiredList store={store} documents={documents} />
              {documents.length === 0 ? (
                <EmptyState icon="clipboard" title={t('sellerSetup.noDocuments')} />
              ) : (
                <div className="table-scroll">
                  <table className="data-table" data-testid="seller-documents">
                    <thead>
                      <tr>
                        <th scope="col">{t('sellerSetup.kind')}</th>
                        <th scope="col">{t('sellerSetup.file')}</th>
                        <th scope="col">{t('sellerSetup.status')}</th>
                        <th scope="col">{t('sellerSetup.uploaded')}</th>
                        <th scope="col"><span className="visually-hidden">{t('market.actions')}</span></th>
                      </tr>
                    </thead>
                    <tbody>
                      {documents.map((d) => (
                        <tr key={d.id}>
                          <td>{t(`sellerSetup.docKind.${d.kind}`)}{d.reference_number ? <div className="text-caption ltr">{d.reference_number}</div> : null}</td>
                          <td>
                            <button type="button" className="link-button" onClick={() => openPrivate(d.file_url, company).catch(fail)}>
                              <Icon name="clipboard" size={14} /> <span className="ltr">{d.original_name}</span>
                            </button>
                            <div className="text-caption">{Math.ceil(d.size / 1024)} KB</div>
                          </td>
                          <td>
                            <Badge tone={DOC_TONE[d.status]}>{t(`sellerSetup.docStatus.${d.status}`)}</Badge>
                            {d.review_note ? <div className="text-caption">{d.review_note}</div> : null}
                          </td>
                          <td>{new Date(d.created_at).toLocaleDateString()}</td>
                          <td>
                            {d.status !== 'APPROVED' ? (
                              <ApiActionButton size="sm" variant="ghost" action={() => mp.withdrawDocument(d.id, company)} onSuccess={() => { clear(); reload() }} onError={fail}>
                                {t('sellerSetup.withdraw')}
                              </ApiActionButton>
                            ) : null}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <UploadForm company={company} defaultKind={store.missing_documents?.[0]} onDone={() => { clear(); reload() }} onError={fail} />
            </SectionCard>
          </>
        )}
      </AsyncPage>
    </>
  )
}

function StoreStatusCard({ store, company, onDone, onError }: { store: MedicalCompany; company?: string; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const status = store.store_status ?? 'ACTIVE'
  const missing = store.missing_documents ?? []
  const verified = store.verification_status === 'VERIFIED'
  return (
    <SectionCard
      headingLevel={2}
      title={t('sellerSetup.store')}
      actions={<Badge tone={STORE_TONE[status]}>{t(`sellerSetup.storeStatus.${status}`)}</Badge>}
    >
      <ol className="stack-xs" data-testid="onboarding-steps" style={{ margin: 0, paddingInlineStart: '1.25rem' }}>
        <li>{t('sellerSetup.step.register')} <Badge tone="success">{t('sellerSetup.done')}</Badge></li>
        <li>{t('sellerSetup.step.documents')} {missing.length ? <Badge tone="warning">{t('sellerSetup.missingDocs', { count: missing.length })}</Badge> : <Badge tone="success">{t('sellerSetup.done')}</Badge>}</li>
        <li>{t('sellerSetup.step.verification')} <Badge tone={verified ? 'success' : 'warning'}>{t(`verification.${store.verification_status}`)}</Badge></li>
        <li>{t('sellerSetup.step.activate')} <Badge tone={STORE_TONE[status]}>{t(`sellerSetup.storeStatus.${status}`)}</Badge></li>
      </ol>
      {store.facility_id ? <p className="text-caption">{t('sellerSetup.pharmacyLinked')}</p> : null}
      <p className="text-caption">{store.can_sell ? t('sellerSetup.selling') : t('sellerSetup.notSelling')}</p>
      <div className="cluster">
        {status !== 'ACTIVE' ? (
          <ApiActionButton action={() => mp.setStoreActive(true, company)} onSuccess={onDone} onError={onError} leading={<Icon name="check" size={16} />} disabled={!verified || missing.length > 0}>
            {t('sellerSetup.activate')}
          </ApiActionButton>
        ) : (
          <ApiActionButton variant="secondary" action={() => mp.setStoreActive(false, company)} onSuccess={onDone} onError={onError}>
            {t('sellerSetup.pause')}
          </ApiActionButton>
        )}
      </div>
      {!verified ? <p className="text-caption">{t('sellerSetup.needVerification')}</p> : null}
    </SectionCard>
  )
}

function RequiredList({ store, documents }: { store: MedicalCompany; documents: SellerDocument[] }) {
  const { t } = useTranslation()
  const required = store.required_documents ?? []
  if (!required.length) return null
  return (
    <ul className="cluster" style={{ listStyle: 'none', padding: 0, margin: 0 }} data-testid="required-documents">
      {required.map((kind) => {
        const approved = documents.some((d) => d.kind === kind && d.status === 'APPROVED')
        const pending = documents.some((d) => d.kind === kind && d.status === 'PENDING')
        return (
          <li key={kind}>
            <Badge tone={approved ? 'success' : pending ? 'warning' : 'neutral'}>
              {approved ? '✓ ' : ''}{t(`sellerSetup.docKind.${kind}`)}
            </Badge>
          </li>
        )
      })}
    </ul>
  )
}

function UploadForm({ company, defaultKind, onDone, onError }: { company?: string; defaultKind?: SellerDocumentKind; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const [kind, setKind] = useState<SellerDocumentKind>(defaultKind ?? 'COMMERCIAL_REGISTRATION')
  const [file, setFile] = useState<File | null>(null)
  const [refNo, setRefNo] = useState('')
  const [expires, setExpires] = useState('')
  const [busy, setBusy] = useState(false)
  const [inputKey, setInputKey] = useState(0)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!file) return
    setBusy(true)
    try {
      await mp.uploadDocument(kind, file, { reference_number: refNo.trim(), expires_on: expires || undefined }, company)
      setFile(null)
      setRefNo('')
      setExpires('')
      setInputKey((k) => k + 1)
      onDone()
    } catch (e) {
      onError(e)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form onSubmit={submit} className="stack-sm card-block" data-testid="document-upload" noValidate>
      <h3 className="text-caption">{t('sellerSetup.uploadTitle')}</h3>
      <div className="cluster" style={{ alignItems: 'flex-end' }}>
        <Select label={t('sellerSetup.kind')} value={kind} onChange={(e) => setKind(e.target.value as SellerDocumentKind)}>
          {DOCUMENT_KINDS.map((k) => (
            <option key={k} value={k}>{t(`sellerSetup.docKind.${k}`)}</option>
          ))}
        </Select>
        <TextField label={t('sellerSetup.referenceNo')} optional maxLength={60} value={refNo} onChange={(e) => setRefNo(e.target.value)} />
        <TextField label={t('sellerSetup.expires')} optional type="date" value={expires} onChange={(e) => setExpires(e.target.value)} />
      </div>
      <label className="stack-xs">
        <span>{t('sellerSetup.chooseFile')}</span>
        <input key={inputKey} type="file" accept="application/pdf,image/jpeg,image/png" onChange={(e) => setFile(e.target.files?.[0] ?? null)} data-testid="document-file" />
        <span className="text-caption">{t('sellerSetup.fileRules')}</span>
      </label>
      <Button type="submit" size="sm" loading={busy} disabled={!file} leading={<Icon name="plus" size={14} />}>
        {t('sellerSetup.upload')}
      </Button>
    </form>
  )
}

// ---- catalogue: SKU, variants, photos ---------------------------------------------------------------
export function CatalogTab({ company }: { company?: string }) {
  const { t, i18n } = useTranslation()
  const { error, fail, clear } = useErrors()
  const [open, setOpen] = useState<string | null>(null)
  return (
    <>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <Alert kind="info">{t('sellerSetup.catalogIntro')}</Alert>
      <AsyncPage load={(signal) => mp.listCompanyProducts(company, 1, signal)} deps={[company]}>
        {(page, reload) =>
          page.results.length === 0 ? (
            <div className="card-block"><EmptyState icon="tag" title={t('company.noProducts')} /></div>
          ) : (
            page.results.map((p) => (
              <SectionCard
                key={p.id}
                headingLevel={2}
                title={pickScript(p.title, i18n.language)}
                description={p.sku ? `SKU ${p.sku}` : undefined}
                actions={
                  <span className="cluster">
                    <Badge tone={p.is_active ? 'success' : 'neutral'}>{p.is_active ? t('company.active') : t('company.inactive')}</Badge>
                    <Button size="sm" variant="secondary" onClick={() => setOpen(open === p.id ? null : p.id)} aria-expanded={open === p.id}>
                      {t('sellerSetup.manage')}
                    </Button>
                  </span>
                }
              >
                <p className="text-caption">
                  {t('sellerSetup.variantCount', { count: p.variants?.length ?? 0 })} · {t('sellerSetup.photoCount', { count: p.images?.length ?? 0 })}
                </p>
                {open === p.id ? <ProductManager product={p} company={company} onDone={() => { clear(); reload() }} onError={fail} /> : null}
              </SectionCard>
            ))
          )
        }
      </AsyncPage>
    </>
  )
}

function ProductManager({ product, company, onDone, onError }: { product: CompanyProduct; company?: string; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const money = useMoney()
  const [sku, setSku] = useState(product.sku ?? '')
  const [label, setLabel] = useState('')
  const [vsku, setVsku] = useState('')
  const [price, setPrice] = useState('')
  const [stock, setStock] = useState('')
  const [photo, setPhoto] = useState<File | null>(null)
  const [photoKey, setPhotoKey] = useState(0)
  const variants: OwnerVariant[] = product.variants ?? []
  const [editing, setEditing] = useState<string | null>(null)
  const addVariant = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await mp.createVariant(product.id, { label: label.trim(), sku: vsku.trim(), price: price.trim() || null, stock_quantity: stock.trim() ? Number(stock) : null }, company)
      setLabel('')
      setVsku('')
      setPrice('')
      setStock('')
      onDone()
    } catch (e) {
      onError(e)
    }
  }
  return (
    <div className="stack" data-testid="product-manager">
      <div className="cluster" style={{ alignItems: 'flex-end' }}>
        <TextField label={t('sellerSetup.productSku')} optional maxLength={64} value={sku} onChange={(e) => setSku(e.target.value)} />
        <ApiActionButton size="sm" variant="secondary" action={() => mp.updateCompanyProduct(product.id, { sku: sku.trim() }, company)} onSuccess={onDone} onError={onError}>
          {t('common.save')}
        </ApiActionButton>
      </div>
      <section className="stack-sm" aria-label={t('sellerSetup.variants')}>
        <h3>{t('sellerSetup.variants')}</h3>
        {variants.length ? (
          <div className="table-scroll">
            <table className="data-table" data-testid="variant-table">
              <thead>
                <tr>
                  <th scope="col">{t('sellerSetup.option')}</th>
                  <th scope="col">SKU</th>
                  <th scope="col" className="num">{t('market.price')}</th>
                  <th scope="col" className="num">{t('market.onHand')}</th>
                  <th scope="col" className="num">{t('market.available')}</th>
                  <th scope="col">{t('sellerSetup.status')}</th>
                </tr>
              </thead>
              <tbody>
                {variants.map((v) => (
                  <tr key={v.id}>
                    <td>{v.label}</td>
                    <td className="ltr">{v.sku}</td>
                    <td className="num ltr">{v.price ? money(v.price) : t('sellerSetup.productPrice')}</td>
                    <td className="num ltr">{v.stock_quantity ?? '—'}</td>
                    <td className="num ltr">{v.available ?? '—'}</td>
                    <td>
                      <span className="cluster">
                        <Button size="sm" variant="ghost" onClick={() => setEditing(editing === v.id ? null : v.id)} aria-expanded={editing === v.id}>
                          {t('sellerSetup.editOption')}
                        </Button>
                        <ApiActionButton size="sm" variant="ghost" action={() => mp.updateVariant(v.id, { is_active: !v.is_active }, company)} onSuccess={onDone} onError={onError}>
                          {v.is_active ? t('sellerSetup.hideOption') : t('sellerSetup.showOption')}
                        </ApiActionButton>
                      </span>
                      {editing === v.id ? <VariantEditForm variant={v} company={company} onDone={() => { setEditing(null); onDone() }} onError={onError} /> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-caption">{t('sellerSetup.noVariants')}</p>
        )}
        <form onSubmit={addVariant} className="cluster" style={{ alignItems: 'flex-end' }} data-testid="variant-form" noValidate>
          <TextField label={t('sellerSetup.option')} required maxLength={80} value={label} onChange={(e) => setLabel(e.target.value)} hint={t('sellerSetup.optionHint')} />
          <TextField label="SKU" required maxLength={64} value={vsku} onChange={(e) => setVsku(e.target.value)} />
          <TextField label={t('market.price')} optional inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value.replace(/[^0-9]/g, ''))} hint={t('sellerSetup.priceHint')} />
          <TextField label={t('sellerSetup.openingStock')} optional inputMode="numeric" value={stock} onChange={(e) => setStock(e.target.value.replace(/[^0-9]/g, ''))} />
          <Button type="submit" size="sm" disabled={!label.trim() || !vsku.trim()}>{t('sellerSetup.addVariant')}</Button>
        </form>
        <p className="text-caption">{t('sellerSetup.variantStockHint')}</p>
      </section>
      <section className="stack-sm" aria-label={t('sellerSetup.photos')}>
        <h3>{t('sellerSetup.photos')}</h3>
        <div className="cluster" data-testid="photo-list">
          {(product.images ?? []).map((ph) => (
            <figure key={ph.id} className="stack-xs" style={{ margin: 0 }}>
              <PrivatePhoto photo={ph} company={company} />
              <ApiActionButton size="sm" variant="ghost" action={() => mp.deleteProductPhoto(ph.id, company)} onSuccess={onDone} onError={onError}>
                {t('store.remove')}
              </ApiActionButton>
            </figure>
          ))}
        </div>
        <div className="cluster" style={{ alignItems: 'flex-end' }}>
          <label className="stack-xs">
            <span>{t('sellerSetup.addPhoto')}</span>
            <input key={photoKey} type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} data-testid="photo-file" />
            <span className="text-caption">{t('sellerSetup.photoRules')}</span>
          </label>
          <ApiActionButton
            size="sm"
            disabled={!photo}
            action={() => mp.uploadProductPhoto(product.id, photo as File, pickScript(product.title, 'en'), company)}
            onSuccess={() => {
              setPhoto(null)
              setPhotoKey((k) => k + 1)
              onDone()
            }}
            onError={onError}
          >
            {t('sellerSetup.upload')}
          </ApiActionButton>
        </div>
      </section>
    </div>
  )
}

/** Edit an option's name, SKU and price (stock changes go through a stock adjustment). */
function VariantEditForm({ variant, company, onDone, onError }: { variant: OwnerVariant; company?: string; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const [label, setLabel] = useState(variant.label)
  const [sku, setSku] = useState(variant.sku)
  const [price, setPrice] = useState(variant.price ? String(Math.round(Number(variant.price))) : '')
  return (
    <div className="cluster" style={{ alignItems: 'flex-end' }} data-testid="variant-edit-form">
      <TextField label={t('sellerSetup.option')} maxLength={80} value={label} onChange={(e) => setLabel(e.target.value)} />
      <TextField label="SKU" maxLength={64} value={sku} onChange={(e) => setSku(e.target.value)} />
      <TextField label={t('market.price')} optional inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value.replace(/[^0-9]/g, ''))} hint={t('sellerSetup.priceHint')} />
      <ApiActionButton size="sm" disabled={!label.trim() || !sku.trim()} action={() => mp.updateVariant(variant.id, { label: label.trim(), sku: sku.trim(), price: price || null }, company)} onSuccess={onDone} onError={onError}>
        {t('common.save')}
      </ApiActionButton>
    </div>
  )
}

// ---- delivery fees and tax treatment ------------------------------------------------------------------
export function DeliveryTab({ company }: { company?: string }) {
  const { t } = useTranslation()
  const { error, fail, clear } = useErrors()
  return (
    <>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <AsyncPage
        load={async (signal) => {
          const [store, rates, governorates] = await Promise.all([
            mp.getStore(company, signal),
            mp.listShippingRates(company, signal),
            reference.listGovernorates(undefined, signal),
          ])
          return { store, rates, governorates }
        }}
        deps={[company]}
      >
        {({ store, rates, governorates }, reload) => (
          <>
            <TaxForm store={store} company={company} onDone={() => { clear(); reload() }} onError={fail} />
            <SectionCard headingLevel={2} title={t('sellerSetup.delivery')} description={t('sellerSetup.deliveryIntro')}>
              <DefaultsForm store={store} company={company} onDone={() => { clear(); reload() }} onError={fail} />
              <RatesTable rates={rates} company={company} onDone={() => { clear(); reload() }} onError={fail} />
              <RateForm governorates={governorates} company={company} onDone={() => { clear(); reload() }} onError={fail} />
            </SectionCard>
          </>
        )}
      </AsyncPage>
    </>
  )
}

function TaxForm({ store, company, onDone, onError }: { store: MedicalCompany; company?: string; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const [mode, setMode] = useState<TaxMode>(store.tax_mode ?? 'NONE')
  const [rate, setRate] = useState(String(Number(store.tax_rate ?? 0) || ''))
  const [label, setLabel] = useState(store.tax_label ?? '')
  const [regNo, setRegNo] = useState(store.tax_registration_number ?? '')
  return (
    <SectionCard headingLevel={2} title={t('sellerSetup.tax')} description={t('sellerSetup.taxIntro')}>
      <Alert kind="warning">{t('sellerSetup.taxDisclaimer')}</Alert>
      <div className="cluster" style={{ alignItems: 'flex-end' }} data-testid="tax-form">
        <Select label={t('sellerSetup.taxMode')} value={mode} onChange={(e) => setMode(e.target.value as TaxMode)}>
          {(['NONE', 'INCLUSIVE', 'EXCLUSIVE'] as TaxMode[]).map((m) => (
            <option key={m} value={m}>{t(`sellerSetup.taxModes.${m}`)}</option>
          ))}
        </Select>
        {mode !== 'NONE' ? (
          <>
            <TextField label={t('sellerSetup.taxRate')} inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value.replace(/[^0-9.]/g, ''))} hint="0–30 %" />
            <TextField label={t('sellerSetup.taxLabel')} optional maxLength={40} value={label} onChange={(e) => setLabel(e.target.value)} />
            <TextField label={t('sellerSetup.taxNumber')} optional maxLength={40} value={regNo} onChange={(e) => setRegNo(e.target.value)} />
          </>
        ) : null}
        <ApiActionButton
          size="sm"
          action={() => mp.updateStoreSettings(mode === 'NONE' ? { tax_mode: 'NONE' } : { tax_mode: mode, tax_rate: rate || '0', tax_label: label.trim(), tax_registration_number: regNo.trim() }, company)}
          onSuccess={onDone}
          onError={onError}
        >
          {t('common.save')}
        </ApiActionButton>
      </div>
    </SectionCard>
  )
}

function DefaultsForm({ store, company, onDone, onError }: { store: MedicalCompany; company?: string; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const [fee, setFee] = useState(store.default_shipping_fee ? String(Math.round(Number(store.default_shipping_fee))) : '')
  const [freeOver, setFreeOver] = useState(store.free_shipping_over ? String(Math.round(Number(store.free_shipping_over))) : '')
  return (
    <div className="cluster" style={{ alignItems: 'flex-end' }} data-testid="delivery-defaults">
      <TextField label={t('sellerSetup.defaultFee')} optional inputMode="numeric" value={fee} onChange={(e) => setFee(e.target.value.replace(/[^0-9]/g, ''))} hint={t('sellerSetup.defaultFeeHint')} />
      <TextField label={t('sellerSetup.freeOver')} optional inputMode="numeric" value={freeOver} onChange={(e) => setFreeOver(e.target.value.replace(/[^0-9]/g, ''))} />
      <ApiActionButton size="sm" variant="secondary" action={() => mp.updateStoreSettings({ default_shipping_fee: fee || null, free_shipping_over: freeOver || null }, company)} onSuccess={onDone} onError={onError}>
        {t('common.save')}
      </ApiActionButton>
    </div>
  )
}

function RatesTable({ rates, company, onDone, onError }: { rates: import('../../api').ShippingRate[]; company?: string; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const money = useMoney()
  if (!rates.length) return <p className="text-caption">{t('sellerSetup.noRates')}</p>
  return (
    <div className="table-scroll">
      <table className="data-table" data-testid="shipping-rates">
        <thead>
          <tr>
            <th scope="col">{t('providers.governorate')}</th>
            <th scope="col" className="num">{t('market.deliveryFee')}</th>
            <th scope="col">{t('sellerSetup.days')}</th>
            <th scope="col"><span className="visually-hidden">{t('market.actions')}</span></th>
          </tr>
        </thead>
        <tbody>
          {rates.map((r) => (
            <tr key={r.id}>
              <td>{name(r.governorate)}</td>
              <td className="num ltr">{money(r.fee)}</td>
              <td className="ltr">{r.min_days}–{r.max_days}</td>
              <td>
                <ApiActionButton size="sm" variant="ghost" action={() => mp.deleteShippingRate(r.id, company)} onSuccess={onDone} onError={onError}>
                  {t('store.remove')}
                </ApiActionButton>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RateForm({ governorates, company, onDone, onError }: { governorates: Governorate[]; company?: string; onDone: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const [governorate, setGovernorate] = useState(governorates[0]?.id ?? '')
  const [fee, setFee] = useState('')
  const [minDays, setMinDays] = useState('1')
  const [maxDays, setMaxDays] = useState('3')
  return (
    <div className="cluster" style={{ alignItems: 'flex-end' }} data-testid="rate-form">
      <Select label={t('providers.governorate')} value={governorate} onChange={(e) => setGovernorate(e.target.value)}>
        {governorates.map((g) => (
          <option key={g.id} value={g.id}>{name(g)}</option>
        ))}
      </Select>
      <TextField label={t('market.deliveryFee')} inputMode="numeric" value={fee} onChange={(e) => setFee(e.target.value.replace(/[^0-9]/g, ''))} />
      <TextField label={t('sellerSetup.minDays')} inputMode="numeric" value={minDays} onChange={(e) => setMinDays(e.target.value.replace(/[^0-9]/g, ''))} />
      <TextField label={t('sellerSetup.maxDays')} inputMode="numeric" value={maxDays} onChange={(e) => setMaxDays(e.target.value.replace(/[^0-9]/g, ''))} />
      <ApiActionButton
        size="sm"
        disabled={!governorate || !fee}
        action={() => mp.setShippingRate({ governorate, fee, min_days: Number(minDays || 0), max_days: Number(maxDays || 0) }, company)}
        onSuccess={() => {
          setFee('')
          onDone()
        }}
        onError={onError}
      >
        {t('sellerSetup.saveRate')}
      </ApiActionButton>
    </div>
  )
}

// ---- accounting report ----------------------------------------------------------------------------------
function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}


export function ReportsTab({ company }: { company?: string }) {
  const { t } = useTranslation()
  const money = useMoney()
  const [from, setFrom] = useState(isoDaysAgo(90))
  const [to, setTo] = useState(isoDaysAgo(0))
  const [range, setRange] = useState({ from, to })
  const { error, fail } = useErrors()
  return (
    <>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <form
        className="cluster"
        style={{ alignItems: 'flex-end' }}
        onSubmit={(e) => {
          e.preventDefault()
          setRange({ from, to })
        }}
      >
        <TextField label={t('sellerSetup.from')} type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        <TextField label={t('sellerSetup.to')} type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        <Button type="submit" size="sm" variant="secondary">{t('sellerSetup.show')}</Button>
        <ApiActionButton
          size="sm"
          leading={<Icon name="clipboard" size={14} />}
          action={() => commerce.downloadSalesReport(range, company)}
          onSuccess={(blob) => downloadBlob(blob as Blob, `racheeta-sales-${range.from}-${range.to}.csv`)}
          onError={fail}
        >
          {t('sellerSetup.downloadCsv')}
        </ApiActionButton>
      </form>
      <AsyncPage load={(signal) => commerce.getSalesReport(range, company, signal)} deps={[range.from, range.to, company]}>
        {(r) => (
          <>
            <Alert kind="info">{t('sellerSetup.commissionNote')}</Alert>
            <div data-testid="report-cards" style={{ display: 'grid', gap: 'var(--space-3)', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
              <StatCard label={t('sellerSetup.orders')} value={String(r.totals.orders)} />
              <StatCard label={t('market.commissionBase')} value={money(r.totals.merchandise_net)} />
              <StatCard label={t('sellerSetup.settledCommission')} value={money(r.totals.settled_commission)} />
              <StatCard label={t('market.deliveryFee')} value={money(r.totals.settled_shipping)} />
              <StatCard label={t('market.tax')} value={money(r.totals.settled_tax)} />
              <StatCard label={t('market.refunded')} value={money(r.totals.refunded)} />
              <StatCard label={t('market.earnings')} value={money(r.totals.settled_earnings)} />
              <StatCard label={t('market.paidOut')} value={money(r.totals.paid_out)} />
            </div>
            {r.months.length ? (
              <SectionCard headingLevel={2} title={t('sellerSetup.byMonth')}>
                <div className="table-scroll">
                  <table className="data-table" data-testid="report-months">
                    <thead>
                      <tr>
                        <th scope="col">{t('sellerSetup.month')}</th>
                        <th scope="col" className="num">{t('sellerSetup.orders')}</th>
                        <th scope="col" className="num">{t('market.commissionBase')}</th>
                        <th scope="col" className="num">{t('sellerSetup.settledCommission')}</th>
                        <th scope="col" className="num">{t('market.earnings')}</th>
                        <th scope="col" className="num">{t('market.paidOut')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {r.months.map((m) => (
                        <tr key={m.month}>
                          <td className="ltr">{m.month}</td>
                          <td className="num ltr">{m.orders ?? 0}</td>
                          <td className="num ltr">{money(m.merchandise_net)}</td>
                          <td className="num ltr">{money(m.commission)}</td>
                          <td className="num ltr">{money(m.earnings)}</td>
                          <td className="num ltr">{money(m.paid_out)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </SectionCard>
            ) : null}
            <SectionCard headingLevel={2} title={t('sellerSetup.orderLines')}>
              {r.orders.length === 0 ? <p className="text-caption">{t('store.noOrders')}</p> : (
                <div className="table-scroll">
                  <table className="data-table" data-testid="report-orders">
                    <thead>
                      <tr>
                        <th scope="col">{t('market.order')}</th>
                        <th scope="col">{t('sellerSetup.placed')}</th>
                        <th scope="col">{t('sellerSetup.status')}</th>
                        <th scope="col" className="num">{t('market.commissionBase')}</th>
                        <th scope="col" className="num">{t('market.commission', { rate: 20 })}</th>
                        <th scope="col" className="num">{t('market.deliveryFee')}</th>
                        <th scope="col" className="num">{t('market.refunded')}</th>
                        <th scope="col" className="num">{t('market.earnings')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {r.orders.map((o) => (
                        <tr key={o.order}>
                          <td className="ltr">{o.order}</td>
                          <td className="ltr">{o.placed}</td>
                          <td>{t(`market.orderStatus.${o.status}`)}{o.settled === 'yes' ? <> · <Badge tone="success">{t('market.accrued')}</Badge></> : null}</td>
                          <td className="num ltr">{money(o.merchandise_net)}</td>
                          <td className="num ltr">{money(o.commission)}</td>
                          <td className="num ltr">{money(o.shipping)}</td>
                          <td className="num ltr">{money(o.refunded)}</td>
                          <td className="num ltr">{money(o.earnings)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </SectionCard>
          </>
        )}
      </AsyncPage>
    </>
  )
}
