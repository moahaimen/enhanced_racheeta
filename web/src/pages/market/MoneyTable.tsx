import type { ReactNode } from 'react'

import { useMoney } from './money'

export interface MoneyRow {
  label: ReactNode
  value: string | number | null | undefined
  /** Shown as a deduction (−). */
  minus?: boolean
  strong?: boolean
  hidden?: boolean
}

/** A small, accessible breakdown table (label → amount). */
export function MoneyTable({ rows, currency = 'IQD', caption }: { rows: MoneyRow[]; currency?: string; caption?: string }) {
  const money = useMoney()
  return (
    <table className="money-table" data-testid="money-table">
      {caption ? <caption className="visually-hidden">{caption}</caption> : null}
      <tbody>
        {rows
          .filter((row) => !row.hidden)
          .map((row, i) => (
            <tr key={i} className={row.strong ? 'money-strong' : undefined}>
              <th scope="row">{row.label}</th>
              <td className="ltr">
                {row.minus && Number(row.value) > 0 ? '− ' : ''}
                {money(row.value, currency)}
              </td>
            </tr>
          ))}
      </tbody>
    </table>
  )
}
