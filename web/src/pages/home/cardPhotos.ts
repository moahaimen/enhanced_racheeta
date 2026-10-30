import doctors from '../../assets/home/svc-doctors.webp'
import estate from '../../assets/home/svc-estate.webp'
import facilities from '../../assets/home/svc-facilities.webp'
import hire from '../../assets/home/svc-hire.webp'
import jobs from '../../assets/home/svc-jobs.webp'
import products from '../../assets/home/svc-products.webp'

/**
 * Photo strips on the six principal homepage cards (owner request after the approved design).
 * Set to `false` to return to the approved icon-only cards — nothing else changes.
 */
export const SHOW_CARD_PHOTOS = true

/** Card key -> photograph (the earlier homepage pictures, see web/src/assets/home/README.md). */
export const CARD_PHOTOS: Record<string, string> = {
  doctors,
  facilities,
  jobs,
  estate,
  products,
  companies: hire,
}
