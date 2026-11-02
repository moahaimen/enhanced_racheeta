/**
 * Approximate centres of Iraq's governorates (keyed by the platform's governorate slug). Used only
 * to pre-select the governorate nearest to a location the user chose to share; the user can always
 * change it, and the server never relies on it.
 */
const CENTRES: Record<string, [number, number]> = {
  baghdad: [33.315, 44.366],
  basra: [30.508, 47.783],
  nineveh: [36.34, 43.13],
  erbil: [36.191, 44.009],
  sulaymaniyah: [35.557, 45.435],
  duhok: [36.867, 42.988],
  kirkuk: [35.468, 44.392],
  diyala: [33.75, 44.64],
  anbar: [33.426, 43.299],
  babil: [32.468, 44.42],
  karbala: [32.616, 44.025],
  najaf: [32.03, 44.34],
  wasit: [32.512, 45.818],
  maysan: [31.836, 47.144],
  'dhi-qar': [31.05, 46.261],
  muthanna: [31.31, 45.28],
  qadisiyyah: [31.993, 44.925],
  saladin: [34.607, 43.678],
  halabja: [35.177, 45.986],
}

export function nearestGovernorateSlug(latitude: number, longitude: number, slugs: string[]): string | null {
  let best: string | null = null
  let bestDistance = Number.POSITIVE_INFINITY
  for (const slug of slugs) {
    const centre = CENTRES[slug]
    if (!centre) continue
    const dLat = centre[0] - latitude
    const dLng = (centre[1] - longitude) * Math.cos((latitude * Math.PI) / 180)
    const distance = dLat * dLat + dLng * dLng
    if (distance < bestDistance) {
      bestDistance = distance
      best = slug
    }
  }
  return best
}
