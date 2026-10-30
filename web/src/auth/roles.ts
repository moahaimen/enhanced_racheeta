import type { AccountRole } from '../api'

/** Roles a visitor may choose. ADMIN is never offered; the backend rejects it anyway. */
export const SELF_REGISTRATION_ROLES: Exclude<AccountRole, 'ADMIN'>[] = [
  'PATIENT',
  'PROVIDER',
  'MEDICAL_COMPANY',
  'REAL_ESTATE_SELLER',
]

import type { AccountType } from '../api'

/** Onboarding account types, grouped for the picker. The server derives the role from the type. */
export const ACCOUNT_TYPE_GROUPS: { group: string; types: AccountType[] }[] = [
  { group: 'people', types: ['PATIENT'] },
  { group: 'practitioners', types: ['DOCTOR', 'NURSE', 'THERAPIST'] },
  { group: 'facilities', types: ['HOSPITAL', 'MEDICAL_CENTER', 'PHARMACY', 'LABORATORY', 'BEAUTY_CENTER'] },
  {
    group: 'business',
    types: [
      'PHARMACEUTICAL_COMPANY',
      'SCIENTIFIC_OFFICE',
      'MEDICAL_SUPPLIES_OFFICE',
      'EQUIPMENT_SUPPLIER',
      'ASSISTIVE_DEVICE_STORE',
      'PHARMA_DISTRIBUTOR',
    ],
  },
  { group: 'property', types: ['PROPERTY_OWNER', 'PROPERTY_AGENT'] },
]

/** Mirror of the server's ACCOUNT_TYPE_ROLE (the server re-derives it and rejects a mismatch). */
export function roleForAccountType(type: AccountType): Exclude<AccountRole, 'ADMIN'> {
  if (type === 'PATIENT') return 'PATIENT'
  if (type === 'PROPERTY_OWNER' || type === 'PROPERTY_AGENT') return 'REAL_ESTATE_SELLER'
  if (ACCOUNT_TYPE_GROUPS[3]!.types.includes(type)) return 'MEDICAL_COMPANY'
  return 'PROVIDER'
}
