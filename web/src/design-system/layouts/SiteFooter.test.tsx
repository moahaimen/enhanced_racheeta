import { screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../../api/endpoints/auth'
import * as notificationsApi from '../../api/endpoints/notifications'
import * as providersApi from '../../api/endpoints/providers'
import * as referenceApi from '../../api/endpoints/reference'
import { tokenStore } from '../../api/tokens'
import { changeLanguage } from '../../i18n'
import { mockHomeData } from '../../test/homeMocks'
import { makeAccount, renderApp } from '../../test/renderApp'

vi.mock('../../api/endpoints/auth')
vi.mock('../../api/endpoints/providers')
vi.mock('../../api/endpoints/reference')
vi.mock('../../api/endpoints/jobs')
vi.mock('../../api/endpoints/realEstate')
vi.mock('../../api/endpoints/marketplace')

type Role = 'PATIENT' | 'PROVIDER' | 'MEDICAL_COMPANY' | 'REAL_ESTATE_SELLER'

async function services(role?: Role) {
  if (role) {
    tokenStore.set({ access: 'a', refresh: 'r' })
    vi.mocked(authApi.getMe).mockResolvedValue(makeAccount({ role }))
    renderApp('/')
    await screen.findByRole('button', { name: /workspace|مساحة/i })
  } else {
    renderApp('/')
  }
  return within(await screen.findByTestId('footer-services'))
}

const hrefs = (list: ReturnType<typeof within>) =>
  list.queryAllByRole('link').map((link: HTMLElement) => link.getAttribute('href'))

describe('SiteFooter services', () => {
  beforeEach(async () => {
    vi.resetAllMocks()
    mockHomeData()
    vi.mocked(notificationsApi.getUnreadCount).mockResolvedValue({ count: 0 })
    vi.mocked(providersApi.listProviders).mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
    vi.mocked(referenceApi.listSpecialties).mockResolvedValue([])
    await changeLanguage('en')
    tokenStore.clear()
  })

  it('never calls a live module "coming soon"', async () => {
    renderApp('/')
    const footer = await screen.findByTestId('site-footer')
    expect(footer).not.toHaveTextContent(/coming (soon|next)/i)
  })

  it('links visitors to the store and to provider offers; the marketplace says who it is for', async () => {
    const list = await services()
    expect(hrefs(list)).toEqual(['/store', '/providers'])
    expect(list.getByText('Medical marketplace')).toBeInTheDocument()
    expect(list.getByText('Verified professionals')).toBeInTheDocument()
  })

  it('a patient gets the same honest links', async () => {
    const list = await services('PATIENT')
    expect(hrefs(list)).toEqual(['/store', '/providers'])
  })

  it('a provider manages its offers and opens the marketplace', async () => {
    const list = await services('PROVIDER')
    expect(hrefs(list)).toEqual(['/store', '/provider/offers', '/marketplace'])
    expect(list.queryByText('Verified professionals')).toBeNull()
  })

  it('a company reaches its seller workspace from the marketplace link', async () => {
    const list = await services('MEDICAL_COMPANY')
    expect(hrefs(list)).toEqual(['/store', '/providers', '/company'])
  })

  it('is translated in Arabic, without «قريباً»', async () => {
    await changeLanguage('ar')
    const list = await services()
    expect(list.getByText('عروض مقدّمي الخدمة')).toBeInTheDocument()
    expect(list.getByText('للمهنيين الموثّقين')).toBeInTheDocument()
    expect(await screen.findByTestId('site-footer')).not.toHaveTextContent('قريباً')
    expect(screen.getByRole('heading', { name: 'الخدمات' })).toBeInTheDocument()
  })
})
