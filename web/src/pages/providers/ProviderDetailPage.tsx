import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'

import { ApiError, providers as providersApi } from '../../api'
import type { ProviderPublic } from '../../api'
import { AsyncPage } from '../../components'
import { useLocalizedName } from '../../i18n/localized'
import { ProviderTypeBadge } from './ProviderBadges'

/** Public provider profile. Everything shown comes from GET /providers/{id}. */
export function ProviderDetailPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()

  const load = async (signal: AbortSignal) => {
    try {
      return await providersApi.getProvider(id, signal)
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        throw new ApiError(404, 'not_found', t('providerDetail.notFound'))
      }
      throw error
    }
  }

  return (
    <AsyncPage load={load} deps={[id]}>
      {(provider) => <ProviderDetail provider={provider} />}
    </AsyncPage>
  )
}

function ProviderDetail({ provider }: { provider: ProviderPublic }) {
  const { t, i18n } = useTranslation()
  const name = useLocalizedName()
  const hasContact = provider.phone || provider.public_email || provider.website || provider.address
  return (
    <>
      <section className="card provider-header">
        {provider.image_url ? (
          <img className="provider-header__image" src={provider.image_url} alt="" />
        ) : null}
        <div>
          <h2>{provider.display_name}</h2>
          <p>
            <ProviderTypeBadge type={provider.provider_type} />{' '}
            <span className="muted">
              {name(provider.governorate)}
              {provider.city ? ` — ${name(provider.city)}` : ''}
            </span>
          </p>
          {provider.verified_at ? (
            <p className="muted">
              {t('providerDetail.verifiedSince')}{' '}
              {new Date(provider.verified_at).toLocaleDateString(i18n.language)}
            </p>
          ) : null}
          <Link to="/providers" className="link">
            {t('providerDetail.backToList')}
          </Link>
        </div>
      </section>

      {provider.about ? (
        <section className="card">
          <h3>{t('providerDetail.about')}</h3>
          <p className="prewrap">{provider.about}</p>
        </section>
      ) : null}

      {provider.specialties.length > 0 ? (
        <section className="card">
          <h3>{t('providerDetail.specialties')}</h3>
          <ul className="chips">
            {provider.specialties.map((s) => (
              <li key={s.id} className="chip">
                {name(s)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="card">
        <h3>{t('providerDetail.services')}</h3>
        {provider.services.length === 0 ? (
          <p className="muted">{t('providerDetail.noServices')}</p>
        ) : (
          <table className="table">
            <tbody>
              {provider.services.map((s) => (
                <tr key={s.id}>
                  <td>
                    <strong>{s.title}</strong>
                    {s.specialty ? <div className="muted">{name(s.specialty)}</div> : null}
                    {s.description ? <div className="muted prewrap">{s.description}</div> : null}
                  </td>
                  <td dir="ltr">
                    {Number(s.price).toLocaleString(i18n.language)} {s.currency}
                  </td>
                  <td>{s.duration_minutes ? t('providerDetail.duration', { minutes: s.duration_minutes }) : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {hasContact || provider.latitude ? (
        <section className="card">
          <h3>{t('providerDetail.contact')}</h3>
          <dl className="status">
            {provider.phone ? (
              <>
                <dt>{t('providerDetail.phone')}</dt>
                <dd dir="ltr">{provider.phone}</dd>
              </>
            ) : null}
            {provider.public_email ? (
              <>
                <dt>{t('providerDetail.email')}</dt>
                <dd dir="ltr">{provider.public_email}</dd>
              </>
            ) : null}
            {provider.website ? (
              <>
                <dt>{t('providerDetail.website')}</dt>
                <dd dir="ltr">
                  <a href={provider.website} rel="noopener noreferrer" target="_blank">
                    {provider.website}
                  </a>
                </dd>
              </>
            ) : null}
            {provider.address ? (
              <>
                <dt>{t('providerDetail.address')}</dt>
                <dd>{provider.address}</dd>
              </>
            ) : null}
            {provider.latitude && provider.longitude ? (
              <>
                <dt>{t('providerDetail.location')}</dt>
                <dd dir="ltr">
                  {provider.latitude}, {provider.longitude}
                </dd>
              </>
            ) : null}
          </dl>
        </section>
      ) : null}

      {provider.related_providers.length > 0 ? (
        <section className="card">
          <h3>{provider.kind === 'PRACTITIONER' ? t('providerDetail.worksAt') : t('providerDetail.team')}</h3>
          <ul className="related-list">
            {provider.related_providers.map((r) => (
              <li key={r.id}>
                <Link to={`/providers/${r.id}`}>{r.display_name}</Link> <ProviderTypeBadge type={r.provider_type} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  )
}
