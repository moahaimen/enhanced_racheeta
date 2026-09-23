import type { Governorate, ProviderCard, ProviderOwner, ProviderPublic, Specialty } from '../api'

export const baghdad: Governorate = {
  id: 'g-baghdad',
  country: 'c-iq',
  slug: 'baghdad',
  name_ar: 'بغداد',
  name_en: 'Baghdad',
}
export const basra: Governorate = { id: 'g-basra', country: 'c-iq', slug: 'basra', name_ar: 'البصرة', name_en: 'Basra' }
export const cardiology: Specialty = {
  id: 's-cardio',
  slug: 'cardiology',
  name_ar: 'أمراض القلب',
  name_en: 'Cardiology',
  parent: null,
}
export const dentistry: Specialty = {
  id: 's-dent',
  slug: 'dentistry',
  name_ar: 'طب الأسنان',
  name_en: 'Dentistry',
  parent: null,
}

export function makeCard(overrides: Partial<ProviderCard> = {}): ProviderCard {
  return {
    id: 'p-1',
    provider_type: 'DOCTOR',
    kind: 'PRACTITIONER',
    display_name: 'Dr Example',
    governorate: baghdad,
    city: null,
    specialties: [cardiology],
    image_url: '',
    ...overrides,
  }
}

export function makePublic(overrides: Partial<ProviderPublic> = {}): ProviderPublic {
  return {
    ...makeCard(),
    about: 'About text',
    phone: '+9647700000000',
    public_email: 'dr@example.com',
    website: 'https://dr.example',
    address: 'Street 1',
    latitude: '33.312800',
    longitude: '44.361500',
    services: [
      {
        id: 'svc-1',
        title: 'Consultation',
        description: '',
        specialty: cardiology,
        price: '25000.00',
        currency: 'IQD',
        duration_minutes: 30,
      },
    ],
    related_providers: [
      { id: 'p-h', provider_type: 'HOSPITAL', kind: 'FACILITY', display_name: 'City Hospital', image_url: '' },
    ],
    verified_at: '2026-09-01T00:00:00Z',
    ...overrides,
  }
}

export function makeOwner(overrides: Partial<ProviderOwner> = {}): ProviderOwner {
  return {
    ...makeCard(),
    can_change_type: true,
    about: '',
    phone: '',
    public_email: '',
    website: '',
    address: '',
    latitude: null,
    longitude: null,
    is_visible: true,
    verification_status: 'UNVERIFIED',
    verification_note: '',
    verification_requested_at: null,
    verification_changed_at: null,
    verified_at: null,
    created_at: '2026-09-23T10:00:00Z',
    updated_at: '2026-09-23T10:00:00Z',
    ...overrides,
  }
}
