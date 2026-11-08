/** Test control for the server product switches (see src/hooks/useFeatures.ts). */
type Flags = { reservations_enabled: boolean }

const DEFAULT: Flags = { reservations_enabled: true } // legacy UI tests run with booking ON
let current: Flags = { ...DEFAULT }

export function testFeatures(): Flags {
  return { ...current }
}

/** Switch online booking for the rest of the current test (reset after each test). */
export function setBookingEnabled(on: boolean) {
  current = { ...current, reservations_enabled: on }
}

export function resetTestFeatures() {
  current = { ...DEFAULT }
}
