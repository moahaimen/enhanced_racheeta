import type { ProviderType, Specialty } from './providers.types'
import type { MarketplaceProduct } from './marketplace.types'
import type { Paginated } from './providers.types'

/** Mirrors backend `apps/advertising/types.py`; the API accepts no other value. */
export const CAMPAIGN_STATUSES = ['DRAFT', 'PENDING_PAYMENT', 'ACTIVE', 'REJECTED', 'CANCELLED'] as const
export type CampaignStatus = (typeof CAMPAIGN_STATUSES)[number]

export type CampaignPaymentStatus = 'PENDING' | 'VERIFIED' | 'REJECTED'

export const PAYMENT_METHODS = ['BANK_TRANSFER', 'CASH', 'EXCHANGE_OFFICE', 'OTHER'] as const
export type CampaignPaymentMethod = (typeof PAYMENT_METHODS)[number]

/** The company's own view of the product a campaign promotes. */
export interface CampaignProduct {
  id: string
  title: string
  brand: string
  model_name: string
  is_active: boolean
  category: { id: string; slug: string; name_ar: string; name_en: string }
}

export interface CampaignGovernorate {
  id: string
  slug: string
  name_ar: string
  name_en: string
  is_active: boolean
}

/** The price snapshot, written once by the backend at submission (never by a client). */
export interface CampaignQuoteSnapshot {
  days: number
  daily_rate: string
  amount: string
  currency: string
  quoted_at: string
}

/** What a company may know about its payment: no admin note, no verifier. */
export interface CampaignPaymentSummary {
  status: CampaignPaymentStatus
  amount: string
  currency: string
  method: CampaignPaymentMethod | ''
  reference: string
  created_at: string
  verified_at: string | null
}

export interface Campaign {
  id: string
  name: string
  product: CampaignProduct
  starts_on: string | null
  ends_on: string | null
  /** Server-owned lifecycle: changes only through submit / cancel / an administrator's payment decision. */
  status: CampaignStatus
  provider_types: ProviderType[]
  specialties: Specialty[]
  governorates: CampaignGovernorate[]
  quote: CampaignQuoteSnapshot | null
  payment: CampaignPaymentSummary | null
  /** Backend-derived: ACTIVE and inside its date window today. */
  is_live: boolean
  /** Backend-derived: ACTIVE past its end date. */
  is_ended: boolean
  created_at: string
  updated_at: string
}

/** The only fields a company may send. Price, payment, status and ownership are server-controlled. */
export interface CampaignWrite {
  name?: string
  product?: string
  starts_on?: string | null
  ends_on?: string | null
  provider_types?: ProviderType[]
  specialties?: string[]
  governorates?: string[]
}

export interface CampaignDashboard {
  campaigns_total: number
  campaigns_draft: number
  campaigns_pending_payment: number
  campaigns_active: number
  campaigns_live: number
  campaigns_ended: number
  campaigns_rejected: number
  campaigns_cancelled: number
}

/** A PREVIEW from the current backend rate; submission recomputes the price under lock. */
export interface CampaignQuote {
  days: number
  daily_rate: string
  total: string
  currency: string
}

/** What an eligible provider sees: the existing product plus the window. Nothing commercial. */
export interface SponsoredCampaign {
  id: string
  sponsored: true
  starts_on: string | null
  ends_on: string | null
  product: MarketplaceProduct
}

export interface AdminCampaignPayment extends CampaignPaymentSummary {
  admin_note: string
  verified_by_email: string | null
}

export interface AdminCampaign extends Omit<Campaign, 'payment'> {
  company: { id: string; name: string; account_email: string }
  payment: AdminCampaignPayment | null
}

/** The administrator's confirmation. The amount is the campaign's own quote: never an input. */
export interface PaymentVerification {
  method: CampaignPaymentMethod
  reference?: string
  note?: string
}

export type PaginatedCampaigns = Paginated<Campaign>
export type PaginatedAdminCampaigns = Paginated<AdminCampaign>
export type PaginatedSponsored = Paginated<SponsoredCampaign>
