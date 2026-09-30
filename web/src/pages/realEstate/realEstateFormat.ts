import type { ContactMethod, OwnerListing } from '../../api'

/** "1,500,000 IQD", or the localized "price on request" when the backend sends null. */
export function formatListingPrice(listing: { price: string | null; currency: string }, language: string, onRequest: string): string {
  if (listing.price === null) return onRequest
  return `${Number(listing.price).toLocaleString(language)} ${listing.currency}`
}

export function formatArea(area: string | null, language: string): string {
  return area === null ? '' : Number(area).toLocaleString(language)
}

/** ISO instant -> the value a `datetime-local` input expects (local time, minutes). */
export function toLocalInput(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** `datetime-local` value -> ISO instant, or null when empty/invalid. */
export function fromLocalInput(value: string): string | null {
  if (!value) return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}

export type Missing = 'title' | 'governorate' | 'area' | 'uses' | 'expiry' | 'contact'

/**
 * UX guidance ONLY: what the loaded data already says would make publication
 * fail. The backend gate is authoritative and is always asked; this just avoids
 * offering a button that is certain to be refused. `activeGovernorateIds` is the
 * active reference list, so a listing whose governorate was since deactivated is
 * reported too.
 */
export function publicationGaps(listing: OwnerListing, activeGovernorateIds: ReadonlySet<string>, now = Date.now()): Missing[] {
  const gaps: Missing[] = []
  if (!listing.title.trim()) gaps.push('title')
  if (!activeGovernorateIds.has(listing.governorate.id)) gaps.push('governorate')
  if (listing.area_sqm === null) gaps.push('area')
  if (listing.suitable_uses.length === 0) gaps.push('uses')
  if (!listing.expires_at || new Date(listing.expires_at).getTime() <= now) gaps.push('expiry')
  const method: ContactMethod = listing.contact_method
  const needsPhone = method === 'PHONE' || method === 'BOTH'
  const needsEmail = method === 'EMAIL' || method === 'BOTH'
  if ((needsPhone && !listing.contact_phone.trim()) || (needsEmail && !listing.contact_email.trim())) gaps.push('contact')
  return gaps
}
