import type { IconName } from '../../icons'

/** One recognisable glyph per profession (healthcare first); unknown values fall back to a briefcase. */
const PROFESSION_ICON: Record<string, IconName> = {
  DOCTOR: 'stethoscope',
  DENTIST: 'tooth',
  PHARMACIST: 'pill',
  PHARMACY_TECHNICIAN: 'pill',
  NURSE: 'heartPulse',
  MIDWIFE: 'baby',
  LAB_TECHNICIAN: 'flask',
  RADIOLOGY_TECHNICIAN: 'scan',
  ANESTHESIA_TECHNICIAN: 'syringe',
  PHYSIOTHERAPIST: 'bone',
  NUTRITIONIST: 'apple',
  PSYCHOLOGIST: 'users',
  MEDICAL_ASSISTANT: 'doctor',
  OPTOMETRIST: 'eye',
  SPEECH_THERAPIST: 'headset',
  ADMINISTRATIVE: 'clipboard',
  HEALTH_ADMINISTRATOR: 'clipboard',
  BIOMEDICAL_ENGINEER: 'wrench',
  ENGINEER: 'wrench',
  MEDICAL_REPRESENTATIVE: 'briefcase',
  SOFTWARE_DEVELOPER: 'laptop',
  IT_SUPPORT: 'laptop',
  NETWORK_ENGINEER: 'network',
  CYBERSECURITY: 'lock',
  DATA_ANALYST: 'chart',
  ACCOUNTANT: 'calculator',
  MARKETING: 'megaphone',
  SALES: 'tag',
  HUMAN_RESOURCES: 'users',
  CUSTOMER_SERVICE: 'headset',
  OTHER: 'hospital',
}

export function professionIcon(profession: string): IconName {
  return PROFESSION_ICON[profession] ?? 'briefcase'
}
