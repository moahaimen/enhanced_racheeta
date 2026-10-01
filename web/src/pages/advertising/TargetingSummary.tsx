import { useTranslation } from 'react-i18next'

import type { Campaign } from '../../api'
import { useLocalizedName } from '../../i18n/localized'

/** Provider types, specialties and governorates a campaign narrows to; none = no extra narrowing. */
export function TargetingSummary({ campaign: c }: { campaign: Pick<Campaign, 'provider_types' | 'specialties' | 'governorates'> }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const parts = [
    ...c.provider_types.map((p) => t(`providerTypes.${p}`)),
    ...c.specialties.map((s) => name(s)),
    ...c.governorates.map((g) => name(g)),
  ]
  return (
    <div className="text-caption" data-testid="campaign-targeting">
      {parts.length > 0 ? `${t('advertising.targetingLabel')}: ${parts.join(' · ')}` : t('advertising.noExtraTargeting')}
    </div>
  )
}
