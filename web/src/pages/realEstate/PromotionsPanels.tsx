import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { workspaces as api } from '../../api'
import type { ListingPromotion, OwnerListing } from '../../api'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Badge,
  Button,
  Checkbox,
  CheckboxGroup,
  EmptyState,
  FormActions,
  Icon,
  SectionCard,
  Select,
  TextField,
} from '../../design-system'
import { toErrorMessage, useAsyncData } from '../../hooks/useAsync'
import { pickScript } from '../../i18n/localized'

const TARGETS = ['DOCTOR', 'NURSE', 'THERAPIST', 'HOSPITAL', 'MEDICAL_CENTER', 'PHARMACY', 'LABORATORY', 'BEAUTY_CENTER']

/**
 * Promoted medical properties for a verified provider who OPTED IN (off by default). The backend
 * returns nothing otherwise; an empty result renders nothing. Every card is labelled sponsored.
 */
export function PromotedPropertiesSection() {
  const { t, i18n } = useTranslation()
  const promoted = useAsyncData((signal) => api.listPromotedListings(signal), [])
  const rows = promoted.data?.results ?? []
  if (promoted.loading || promoted.error || rows.length === 0) return null
  return (
    <SectionCard title={t('promo.promotedProperties')} description={t('promo.promotedHint')} headingLevel={2}>
      <ul className="stack" style={{ listStyle: 'none', padding: 0, margin: 0 }} data-testid="promoted-properties">
        {rows.map((row) => (
          <li key={row.promotion_id} className="card-block cluster">
            <Badge tone="warning"><Icon name="tag" size={12} /> {t('promo.sponsored')}</Badge>
            <Link to={`/real-estate/${row.listing.id}`}><strong>{pickScript(row.listing.title, i18n.language)}</strong></Link>
          </li>
        ))}
      </ul>
    </SectionCard>
  )
}

const TONE = { REQUESTED: 'warning', ACTIVE: 'success', REJECTED: 'error', ENDED: 'neutral' } as const

/** Seller side: request a promotion for one of the seller's published listings, or stop one. */
export function SellerPromotionsPanel({ listings }: { listings: OwnerListing[] }) {
  const { t, i18n } = useTranslation()
  const [version, setVersion] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [listing, setListing] = useState('')
  const [days, setDays] = useState('14')
  const [targets, setTargets] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const published = listings.filter((l) => l.publication_status === 'PUBLISHED')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.requestPromotion(listing, targets, Number(days))
      setVersion((v) => v + 1)
    } catch (e) {
      setError(toErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard title={t('promo.promotions')} headingLevel={2}>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <AsyncPage load={(signal) => api.listMyPromotions(signal)} deps={[version]}>
        {(page) =>
          page.results.length === 0 ? (
            <p className="text-secondary">{t('promo.none')}</p>
          ) : (
            <ul className="stack-sm" style={{ listStyle: 'none', padding: 0, margin: 0 }} data-testid="seller-promotions">
              {page.results.map((promo: ListingPromotion) => (
                <li key={promo.id} className="card-block cluster">
                  <strong>{pickScript(promo.listing.title, i18n.language)}</strong>
                  <Badge tone={TONE[promo.status]}>{t(`promo.status.${promo.status}`)}</Badge>
                  {promo.reject_reason ? <span className="text-caption">{promo.reject_reason}</span> : null}
                  {promo.status === 'REQUESTED' || promo.status === 'ACTIVE' ? (
                    <ApiActionButton size="sm" variant="ghost" action={() => api.endPromotion(promo.id)} onSuccess={() => setVersion((v) => v + 1)} onError={(e) => setError(toErrorMessage(e))}>
                      {t('promo.end')}
                    </ApiActionButton>
                  ) : null}
                </li>
              ))}
            </ul>
          )
        }
      </AsyncPage>
      {published.length > 0 ? (
        <form onSubmit={submit} className="stack-sm" data-testid="promotion-form">
          <Select label={t('nav.realEstate')} required value={listing} onChange={(e) => setListing(e.target.value)}>
            <option value="" />
            {published.map((l) => <option key={l.id} value={l.id}>{pickScript(l.title, i18n.language)}</option>)}
          </Select>
          <TextField label={t('promo.days')} type="number" min={1} max={60} required value={days} onChange={(e) => setDays(e.target.value)} />
          <CheckboxGroup legend={t('promo.targets')}>
            {TARGETS.map((target) => (
              <Checkbox
                key={target}
                label={t(`providerTypes.${target}`)}
                checked={targets.includes(target)}
                onChange={(e) => setTargets(e.target.checked ? [...targets, target] : targets.filter((x) => x !== target))}
              />
            ))}
          </CheckboxGroup>
          <FormActions>
            <Button type="submit" loading={busy}>{t('promo.request')}</Button>
          </FormActions>
        </form>
      ) : null}
    </SectionCard>
  )
}

/** Administrator: review requested promotions. */
export function AdminPromotionsPanel() {
  const { t } = useTranslation()
  const [version, setVersion] = useState(0)
  const [error, setError] = useState<string | null>(null)
  return (
    <SectionCard title={t('promo.adminTitle')} headingLevel={2}>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <AsyncPage load={(signal) => api.listAdminPromotions('REQUESTED', signal)} deps={[version]}>
        {(page) =>
          page.results.length === 0 ? (
            <EmptyState icon="home" title={t('promo.none')} />
          ) : (
            <ul className="stack-sm" style={{ listStyle: 'none', padding: 0, margin: 0 }} data-testid="admin-promotions">
              {page.results.map((promo) => (
                <AdminPromotionRow key={promo.id} promo={promo} onDone={() => setVersion((v) => v + 1)} onError={setError} />
              ))}
            </ul>
          )
        }
      </AsyncPage>
    </SectionCard>
  )
}

function AdminPromotionRow({ promo, onDone, onError }: { promo: ListingPromotion; onDone: () => void; onError: (m: string) => void }) {
  const { t, i18n } = useTranslation()
  const [reason, setReason] = useState('')
  return (
    <li className="card-block stack-sm">
      <div className="cluster">
        <strong>{pickScript(promo.listing.title, i18n.language)}</strong>
        <span className="text-caption">
          {promo.days} · {promo.target_provider_types.map((x) => t(`providerTypes.${x}`)).join(' / ') || '—'}
        </span>
      </div>
      <div className="cluster">
        <ApiActionButton size="sm" action={() => api.approvePromotion(promo.id)} onSuccess={onDone} onError={(e) => onError(toErrorMessage(e))}>
          {t('promo.approve')}
        </ApiActionButton>
        <TextField label={t('promo.rejectReason')} maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} />
        <ApiActionButton
          size="sm"
          variant="ghost"
          disabled={!reason.trim()}
          action={() => api.rejectPromotion(promo.id, reason.trim())}
          onSuccess={onDone}
          onError={(e) => onError(toErrorMessage(e))}
        >
          {t('promo.reject')}
        </ApiActionButton>
      </div>
    </li>
  )
}
