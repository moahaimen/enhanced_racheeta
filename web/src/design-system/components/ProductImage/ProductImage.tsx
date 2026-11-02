import { useState } from 'react'

import styles from './ProductImage.module.css'

const PLACEHOLDER = '/products/placeholder.svg'

/** Product photo in a fixed 4:3 frame; a missing or broken image shows a neutral placeholder. */
export function ProductImage({ src, alt, size = 'md' }: { src?: string | null; alt: string; size?: 'sm' | 'md' | 'lg' }) {
  const [failed, setFailed] = useState(false)
  const url = !src || failed ? PLACEHOLDER : src
  return (
    <div className={`${styles.frame} ${styles[size]}`}>
      <img className={styles.image} src={url} alt={alt} loading="lazy" onError={() => setFailed(true)} />
    </div>
  )
}
