import type { ProviderType } from '../../../api'
import type { IconName } from '../../icons'

export const PROVIDER_TYPE_ICON: Record<ProviderType, IconName> = {
  DOCTOR: 'stethoscope',
  NURSE: 'heartPulse',
  THERAPIST: 'users',
  HOSPITAL: 'hospital',
  MEDICAL_CENTER: 'building',
  PHARMACY: 'pill',
  LABORATORY: 'flask',
  BEAUTY_CENTER: 'sparkle',
}
