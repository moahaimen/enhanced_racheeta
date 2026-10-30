import { useSyncExternalStore } from 'react'

/**
 * The cart is a per-browser convenience: product ids, a display snapshot and quantities only.
 * Prices shown from it are estimates — the server re-reads every price and stock figure at
 * checkout and computes the total itself. Storage can be unavailable (private mode), so every
 * access is guarded and the cart then simply lives in memory.
 */
export interface CartLine {
  product: string
  title: string
  price: string
  currency: string
  merchantId: string
  merchantName: string
  quantity: number
}

const KEY = 'racheeta.cart.v1'
const MAX_QUANTITY = 20
let lines: CartLine[] = read()
const listeners = new Set<() => void>()

function read(): CartLine[] {
  try {
    const raw = window.localStorage.getItem(KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? (parsed as CartLine[]).filter((l) => typeof l?.product === 'string') : []
  } catch {
    return []
  }
}

function commit(next: CartLine[]) {
  lines = next
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    /* storage unavailable: keep the in-memory cart */
  }
  listeners.forEach((fn) => fn())
}

export const cart = {
  add(line: Omit<CartLine, 'quantity'>, quantity = 1) {
    const existing = lines.find((l) => l.product === line.product)
    if (existing) {
      commit(lines.map((l) => (l.product === line.product ? { ...l, quantity: Math.min(MAX_QUANTITY, l.quantity + quantity) } : l)))
    } else {
      commit([...lines, { ...line, quantity: Math.min(MAX_QUANTITY, quantity) }])
    }
  },
  setQuantity(product: string, quantity: number) {
    commit(lines.map((l) => (l.product === product ? { ...l, quantity: Math.max(1, Math.min(MAX_QUANTITY, quantity)) } : l)))
  },
  remove(product: string) {
    commit(lines.filter((l) => l.product !== product))
  },
  removeMerchant(merchantId: string) {
    commit(lines.filter((l) => l.merchantId !== merchantId))
  },
  clear() {
    commit([])
  },
}

function subscribe(fn: () => void) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function useCart(): CartLine[] {
  return useSyncExternalStore(subscribe, () => lines, () => lines)
}
