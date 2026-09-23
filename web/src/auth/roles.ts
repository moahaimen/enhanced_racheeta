import type { AccountRole } from '../api'

/** Roles a visitor may choose. ADMIN is never offered; the backend rejects it anyway. */
export const SELF_REGISTRATION_ROLES: Exclude<AccountRole, 'ADMIN'>[] = [
  'PATIENT',
  'PROVIDER',
  'MEDICAL_COMPANY',
  'REAL_ESTATE_SELLER',
]
