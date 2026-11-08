import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Icon } from '../../icons'
import { Alert } from '../Alert/Alert'
import { Button } from '../Button/Button'
import { TextField } from './fields'
import styles from './LocationPicker.module.css'

// Iraq, generously bounded: a point outside gets a gentle warning (never blocked).
const IRAQ = { minLat: 29, maxLat: 37.5, minLng: 38.7, maxLng: 48.8 }

export interface LocationPickerProps {
  latitude: string
  longitude: string
  onChange: (latitude: string, longitude: string) => void
  error?: string | undefined
}

type Status = 'idle' | 'locating' | 'denied' | 'unavailable' | 'unsupported'

/**
 * "Use my current location": the BROWSER asks the user for permission (no coordinates are typed
 * or guessed). The position is used only to fill this form; nothing is sent until the user saves.
 * Manual coordinates stay available under "enter manually" for desk work or a different address.
 */
export function LocationPicker({ latitude, longitude, onChange, error }: LocationPickerProps) {
  const { t } = useTranslation()
  const [status, setStatus] = useState<Status>('idle')
  const [manual, setManual] = useState(false)
  const has = latitude !== '' && longitude !== ''
  const lat = Number(latitude)
  const lng = Number(longitude)
  const outsideIraq = has && (lat < IRAQ.minLat || lat > IRAQ.maxLat || lng < IRAQ.minLng || lng > IRAQ.maxLng)

  const locate = () => {
    if (!('geolocation' in navigator)) {
      setStatus('unsupported')
      return
    }
    setStatus('locating')
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setStatus('idle')
        onChange(position.coords.latitude.toFixed(6), position.coords.longitude.toFixed(6))
      },
      (failure) => setStatus(failure.code === failure.PERMISSION_DENIED ? 'denied' : 'unavailable'),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    )
  }

  return (
    <fieldset className={styles.box} data-testid="location-picker">
      <legend className={styles.legend}>{t('location.title')}</legend>
      <p className="text-caption">{t('location.explain')}</p>
      {has ? (
        <div className={styles.found} data-testid="location-set">
          <Icon name="mapPin" size={18} />
          <span>{t('location.set')}</span>
          <a
            href={`https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=17/${lat}/${lng}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            {t('location.viewMap')}
          </a>
          <Button size="sm" variant="ghost" onClick={() => onChange('', '')}>
            {t('location.clear')}
          </Button>
        </div>
      ) : null}
      {outsideIraq ? <Alert kind="warning">{t('location.outsideIraq')}</Alert> : null}
      {status === 'denied' ? <Alert kind="warning">{t('location.denied')}</Alert> : null}
      {status === 'unavailable' ? <Alert kind="warning">{t('location.unavailable')}</Alert> : null}
      {status === 'unsupported' ? <Alert kind="warning">{t('location.unsupported')}</Alert> : null}
      {error ? <Alert kind="error">{error}</Alert> : null}
      <div className={styles.actions}>
        <Button
          size="sm"
          onClick={locate}
          loading={status === 'locating'}
          loadingLabel={t('location.locating')}
          leading={<Icon name="mapPin" size={16} />}
        >
          {has ? t('location.update') : t('location.useMine')}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setManual((v) => !v)} aria-expanded={manual}>
          {t('location.manual')}
        </Button>
      </div>
      {manual ? (
        <div className="grid-2">
          <TextField
            label={t('location.latitude')}
            dir="ltr"
            inputMode="decimal"
            value={latitude}
            onChange={(e) => onChange(e.target.value.replace(/[^\d.-]/g, ''), longitude)}
          />
          <TextField
            label={t('location.longitude')}
            dir="ltr"
            inputMode="decimal"
            value={longitude}
            onChange={(e) => onChange(latitude, e.target.value.replace(/[^\d.-]/g, ''))}
          />
        </div>
      ) : null}
    </fieldset>
  )
}
