export function tabPanelProps(baseId: string, id: string) {
  return { role: 'tabpanel', id: `${baseId}-panel-${id}`, 'aria-labelledby': `${baseId}-tab-${id}` } as const
}
