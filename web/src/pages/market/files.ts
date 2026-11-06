/** Saves a downloaded file (CSV report, …) under `name` without leaving the page. */
export function downloadBlob(blob: Blob, name: string) {
  const href = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = href
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.setTimeout(() => URL.revokeObjectURL(href), 10_000)
}
