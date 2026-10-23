import { Icon } from '../../design-system'
import doctor from '../../assets/home/hero-doctor.webp'
import doctorSmall from '../../assets/home/hero-doctor-sm.webp'
import { HeroBackdrop } from './art'
import styles from './Home.module.css'

/**
 * Hero composition: project-owned SVG backdrop (towers, palms, orb) + one optimised practitioner
 * photograph (derived from the owner-approved concept art, cut out, no text, WebP 23 kB / 14 kB for
 * narrow screens) + a real-HTML floating chip. Decorative: the image has empty alt text and the
 * block is hidden from assistive technology.
 */
export function HeroVisual({ chip }: { chip: string }) {
  return (
    <div className={styles.heroVisual} aria-hidden="true">
      <HeroBackdrop className={styles.heroBackdrop} />
      <picture>
        <source media="(max-width: 767px)" srcSet={doctorSmall} width={360} height={328} />
        <img className={styles.heroDoctor} src={doctor} width={560} height={511} alt="" fetchPriority="high" decoding="async" />
      </picture>
      <span className={styles.heroChip}>
        <Icon name="heartPulse" size={22} />
        {chip}
      </span>
    </div>
  )
}
