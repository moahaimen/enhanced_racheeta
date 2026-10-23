import { vi } from 'vitest'

import * as jobsApi from '../api/endpoints/jobs'
import * as marketplaceApi from '../api/endpoints/marketplace'
import * as providersApi from '../api/endpoints/providers'
import * as realEstateApi from '../api/endpoints/realEstate'
import * as referenceApi from '../api/endpoints/reference'

export const emptyPage = { count: 0, next: null, previous: null, results: [] }

/**
 * The homepage loads several public lists. Tests that automock an API module (`vi.mock`) must give
 * every function the page calls a value; this fills the ones that are mocked in the current file
 * with empty data and leaves unmocked modules alone.
 */
export function mockHomeData(): void {
  const set = (fn: unknown, value: unknown) => {
    if (vi.isMockFunction(fn)) fn.mockResolvedValue(value)
  }
  set(referenceApi.listGovernorates, [])
  set(referenceApi.listSpecialties, [])
  set(providersApi.listProviders, emptyPage)
  set(jobsApi.listJobs, emptyPage)
  set(realEstateApi.listListings, emptyPage)
  set(marketplaceApi.listCategories, [])
  set(marketplaceApi.listTargetedProducts, emptyPage)
}
