/** Types mirror the OpenAPI contract in docs/api/openapi.yaml. */

export type AccountRole =
  | 'PATIENT'
  | 'PROVIDER'
  | 'MEDICAL_COMPANY'
  | 'REAL_ESTATE_SELLER'
  | 'ADMIN'

export type PreferredLanguage = 'ar' | 'en'

/** Onboarding account type; the server derives the account role from it. */
export type AccountType =
  | 'PATIENT'
  | 'JOB_SEEKER'
  | 'EMPLOYER'
  | 'DOCTOR'
  | 'DENTIST'
  | 'NURSE'
  | 'MIDWIFE'
  | 'THERAPIST'
  | 'HOSPITAL'
  | 'MEDICAL_CENTER'
  | 'PHARMACY'
  | 'LABORATORY'
  | 'BEAUTY_CENTER'
  | 'PHARMACEUTICAL_COMPANY'
  | 'SCIENTIFIC_OFFICE'
  | 'MEDICAL_SUPPLIES_OFFICE'
  | 'EQUIPMENT_SUPPLIER'
  | 'ASSISTIVE_DEVICE_STORE'
  | 'PHARMA_DISTRIBUTOR'
  | 'PROPERTY_OWNER'
  | 'PROPERTY_AGENT'

export interface Account {
  id: string
  email: string
  full_name: string
  phone_number: string
  role: AccountRole
  account_type?: AccountType | ''
  preferred_language: PreferredLanguage
  email_verified: boolean
  email_verified_at: string | null
  has_password: boolean
  is_staff: boolean
  permissions: string[]
  created_at: string
  last_login: string | null
}

export interface TokenPair {
  access: string
  refresh: string
}

export interface RegisterRequest {
  email: string
  password: string
  full_name: string
  phone_number?: string
  role?: Exclude<AccountRole, 'ADMIN'>
  account_type?: AccountType
  preferred_language?: PreferredLanguage
}

export interface RegisterResponse {
  account: Account
  tokens: TokenPair
}

export interface LoginRequest {
  email: string
  password: string
}

export interface UpdateMeRequest {
  full_name?: string
  phone_number?: string
  preferred_language?: PreferredLanguage
}

export interface PasswordResetRequest {
  email: string
}

export interface PasswordResetConfirmRequest {
  uid: string
  token: string
  new_password: string
}

export interface EmailVerificationConfirmRequest {
  uid: string
  token: string
}

export interface DetailResponse {
  detail: string
}

export interface HealthResponse {
  status: 'ok'
}

/** Error envelope returned by every failing API call (docs/API.md). */
export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details?: Record<string, string[]>
    codes?: Record<string, string[]>
    meta?: Record<string, string | number>
  }
}
