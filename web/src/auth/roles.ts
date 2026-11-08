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
  { group: 'people', types: ['PATIENT', 'JOB_SEEKER', 'EMPLOYER'] },
  { group: 'practitioners', types: ['DOCTOR', 'DENTIST', 'NURSE', 'MIDWIFE', 'THERAPIST'] },
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
  if (type === 'PATIENT' || type === 'JOB_SEEKER' || type === 'EMPLOYER') return 'PATIENT'
  if (type === 'PROPERTY_OWNER' || type === 'PROPERTY_AGENT') return 'REAL_ESTATE_SELLER'
  if (ACCOUNT_TYPE_GROUPS[3]!.types.includes(type)) return 'MEDICAL_COMPANY'
  return 'PROVIDER'
}

/** Mirror of the server's ACCOUNT_TYPE_PROVIDER: what the provider form preselects (UX only). */
export const ACCOUNT_TYPE_PROVIDER: Partial<Record<AccountType, { providerType: string; specialty: string | null }>> = {
  DOCTOR: { providerType: 'DOCTOR', specialty: null },
  DENTIST: { providerType: 'DOCTOR', specialty: 'dentistry' },
  NURSE: { providerType: 'NURSE', specialty: null },
  MIDWIFE: { providerType: 'NURSE', specialty: 'midwifery' },
  THERAPIST: { providerType: 'THERAPIST', specialty: null },
  HOSPITAL: { providerType: 'HOSPITAL', specialty: null },
  MEDICAL_CENTER: { providerType: 'MEDICAL_CENTER', specialty: null },
  PHARMACY: { providerType: 'PHARMACY', specialty: null },
  LABORATORY: { providerType: 'LABORATORY', specialty: null },
  BEAUTY_CENTER: { providerType: 'BEAUTY_CENTER', specialty: null },
}
