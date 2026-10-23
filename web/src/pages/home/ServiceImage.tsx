import doctors from '../../assets/home/svc-doctors.webp'
import estate from '../../assets/home/svc-estate.webp'
import facilities from '../../assets/home/svc-facilities.webp'
import hire from '../../assets/home/svc-hire.webp'
import jobs from '../../assets/home/svc-jobs.webp'
import products from '../../assets/home/svc-products.webp'

const IMAGES = { doctors, facilities, products, jobs, estate, hire } as const

/** Decorative card photograph (WebP, 6–13 kB, lazy): the card's text carries the meaning. */
export function ServiceImage({ name }: { name: keyof typeof IMAGES }) {
  return <img src={IMAGES[name]} width={520} height={156} alt="" loading="lazy" decoding="async" />
}
