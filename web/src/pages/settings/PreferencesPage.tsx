import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { workspaces as api } from '../../api'
import type { MarketingPreferences } from '../../api'
import { Alert, AsyncPage, Checkbox, Container, Icon, PageHeader, PageStack, SectionCard } from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'

const GROUPS: { title: string; fields: (keyof MarketingPreferences)[]; locked?: (keyof MarketingPreferences)[] }[] = [
  { title: 'prefs.display', fields: ['show_sponsored_products'] },
  { title: 'prefs.outreach', fields: ['offers_and_news', 'real_estate_promotions', 'job_alerts'] },
  // No external e-mail or push is sent by the local demo, so those channels stay switched off here.
  { title: 'prefs.channels', fields: ['channel_in_app', 'channel_email', 'channel_push'], locked: ['channel_email', 'channel_push'] },
]

/** /settings/preferences — display preference and outreach consent, saved per switch. */
export function PreferencesPage() {
  const { t } = useTranslation()
  return (
    <Container width="lg">
      <PageHeader eyebrow={<><Icon name="bell" size={16} />{t('nav.preferences')}</>} title={t('prefs.title')} description={t('prefs.intro')} />
      <PageStack>
        <AsyncPage load={(signal) => api.getPreferences(signal)}>{(prefs) => <PreferenceForm initial={prefs} />}</AsyncPage>
      </PageStack>
    </Container>
  )
}

function PreferenceForm({ initial }: { initial: MarketingPreferences }) {
  const { t } = useTranslation()
  const [prefs, setPrefs] = useState(initial)
  const [status, setStatus] = useState<{ ok?: boolean; error?: string }>({})
  const toggle = async (field: keyof MarketingPreferences, value: boolean) => {
    const previous = prefs
    setPrefs({ ...prefs, [field]: value })
    try {
      setPrefs(await api.updatePreferences({ [field]: value }))
      setStatus({ ok: true })
    } catch (e) {
      setPrefs(previous)
      setStatus({ error: toErrorMessage(e) })
    }
  }
  return (
    <>
      {status.ok ? <Alert kind="success">{t('prefs.saved')}</Alert> : null}
      {status.error ? <Alert kind="error">{status.error}</Alert> : null}
      {GROUPS.map((group) => (
        <SectionCard key={group.title} title={t(group.title)} headingLevel={2}>
          <div className="stack-sm">
            {group.fields.map((field) => (
              <Checkbox
                key={field}
                label={t(`prefs.${field}`)}
                checked={prefs[field]}
                disabled={group.locked?.includes(field)}
                onChange={(e) => void toggle(field, e.target.checked)}
                data-testid={`pref-${field}`}
              />
            ))}
          </div>
        </SectionCard>
      ))}
    </>
  )
}
