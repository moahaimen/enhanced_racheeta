import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { changeLanguage, initI18n } from '../../../i18n'
import { LocationPicker } from './LocationPicker'

function Harness() {
  const [loc, setLoc] = useState({ lat: '', lng: '' })
  return (
    <>
      <LocationPicker latitude={loc.lat} longitude={loc.lng} onChange={(lat, lng) => setLoc({ lat, lng })} />
      <output data-testid="value">{`${loc.lat},${loc.lng}`}</output>
    </>
  )
}

const original = navigator.geolocation

beforeAll(async () => {
  initI18n()
  await changeLanguage('ar')
})

afterEach(() => {
  Object.defineProperty(navigator, 'geolocation', { value: original, configurable: true })
})

describe('LocationPicker', () => {
  it('asks the browser for the position and fills the coordinates (no typing needed)', async () => {
    const getCurrentPosition = vi.fn((ok: PositionCallback) =>
      ok({ coords: { latitude: 33.312805, longitude: 44.361488 } } as GeolocationPosition),
    )
    Object.defineProperty(navigator, 'geolocation', { value: { getCurrentPosition }, configurable: true })
    render(<Harness />)
    expect(screen.queryByLabelText(/خط العرض|latitude/i)).toBeNull() // manual entry is hidden by default
    await userEvent.click(screen.getByRole('button', { name: /استخدم موقعي الحالي|use my current location/i }))
    expect(getCurrentPosition).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('value')).toHaveTextContent('33.312805,44.361488')
    expect(screen.getByTestId('location-set')).toBeInTheDocument()
  })

  it('explains a refused permission instead of failing silently', async () => {
    const getCurrentPosition = vi.fn((_ok: PositionCallback, fail?: PositionErrorCallback | null) =>
      fail?.({ code: 1, PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3, message: '' } as GeolocationPositionError),
    )
    Object.defineProperty(navigator, 'geolocation', { value: { getCurrentPosition }, configurable: true })
    render(<Harness />)
    await userEvent.click(screen.getByRole('button', { name: /استخدم موقعي الحالي|use my current location/i }))
    expect(screen.getByText(/لم تسمح بمعرفة الموقع|permission was not granted/i)).toBeInTheDocument()
    expect(screen.getByTestId('value')).toHaveTextContent(/^,$/)
  })
})
