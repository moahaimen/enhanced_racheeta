import { useEffect, useSyncExternalStore } from 'react'

import { getFeatures, type PlatformFeatures } from '../api/endpoints/platform'

/**
 * Product switches from `GET /api/v1/platform/features`, fetched once per page load and shared by
 * every component. Fail-closed: until the server answers (or if it cannot be reached) booking is
 * treated as OFF, so no booking entry point flashes in and then disappears.
 */
type State = { features: PlatformFeatures; loaded: boolean }

const OFF: PlatformFeatures = { reservations_enabled: false }
let state: State = { features: OFF, loaded: false }
let inflight: Promise<void> | null = null
const listeners = new Set<() => void>()

function publish(next: State) {
  state = next
  listeners.forEach((listener) => listener())
}

function load() {
  if (inflight) return
  inflight = Promise.resolve()
    .then(() => getFeatures())
    .then((features) => publish({ features: { reservations_enabled: features?.reservations_enabled === true }, loaded: true }))
    .catch(() => publish({ features: OFF, loaded: true }))
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useFeatures(): State & { reservationsEnabled: boolean } {
  useEffect(load, [])
  const current = useSyncExternalStore(subscribe, () => state)
  return { ...current, reservationsEnabled: current.features.reservations_enabled }
}

/** Tests only: forget the cached answer so the next render fetches again. */
export function resetFeaturesForTests() {
  inflight = null
  state = { features: OFF, loaded: false }
}
