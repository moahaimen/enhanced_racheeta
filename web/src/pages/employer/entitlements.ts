import type { BillingSummary } from '../../api'

/**
 * A capability is granted only by an explicit `enabled: true` row of the organisation's billing
 * summary. Loading, errors, missing rows and unknown keys all fail closed: the backend stays
 * authoritative, this only keeps the UI from offering actions it would always refuse.
 */
export function entitled(billing: BillingSummary | null | undefined, key: string): boolean {
  return billing?.entitlements?.find((e) => e.key === key)?.enabled === true
}
