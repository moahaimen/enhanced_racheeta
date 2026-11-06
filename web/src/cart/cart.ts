import { useSyncExternalStore } from 'react'

/**
 * The cart is a per-browser convenience: product ids, a display snapshot and quantities only.
 * Prices shown from it are estimates — the server re-reads every price and stock figure at
 * checkout and computes the total itself. Storage can be unavailable (private mode), so every
 * access is guarded and the cart then simply lives in memory.
 */
export interface CartLine {
  product: string
  /** The chosen option (size, pack...) when the product has variants. */
  variant?: string
  variantLabel?: string
  title: string
  price: string
  currency: string
  merchantId: string
  merchantName: string
  /** Display snapshot only (the server re-reads the product at checkout). */
  image?: string
  /** 'B2B': bought from the professional catalogue (re-read there, not in the public store). */
  source?: 'STORE' | 'B2B'
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

/** One cart line per product AND option; a product without options keeps its id as the key. */
export function lineKey(line: Pick<CartLine, 'product' | 'variant'>): string {
  return line.variant ? `${line.product}:${line.variant}` : line.product
}

export const cart = {
  add(line: Omit<CartLine, 'quantity'>, quantity = 1) {
    const key = lineKey(line)
    const existing = lines.find((l) => lineKey(l) === key)
    if (existing) {
      commit(lines.map((l) => (lineKey(l) === key ? { ...l, quantity: Math.min(MAX_QUANTITY, l.quantity + quantity) } : l)))
    } else {
      commit([...lines, { ...line, quantity: Math.min(MAX_QUANTITY, quantity) }])
    }
  },
  /** `key` is lineKey(line) (the product id for a product without options). */
  setQuantity(key: string, quantity: number) {
    commit(lines.map((l) => (lineKey(l) === key ? { ...l, quantity: Math.max(1, Math.min(MAX_QUANTITY, quantity)) } : l)))
  },
  remove(key: string) {
    commit(lines.filter((l) => lineKey(l) !== key))
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

/** Total number of units in the cart (for the header badge). */
export function useCartCount(): number {
  return useCart().reduce((n, line) => n + line.quantity, 0)
}

export const MAX_CART_QUANTITY = MAX_QUANTITY

export function useCart(): CartLine[] {
  return useSyncExternalStore(subscribe, () => lines, () => lines)
}
