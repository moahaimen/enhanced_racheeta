import type { RouteObject } from 'react-router'

import { AppLayout } from './AppLayout'
import { PublicOnly, RequireAuth, RequireRole, RequireStaff } from './guards'
import { AdminConsolePage } from '../pages/admin/AdminConsolePage'
import { ApplicantsPage } from '../pages/employer/ApplicantsPage'
import { EmployerWorkspacePage } from '../pages/employer/EmployerWorkspacePage'
import { JobEditorPage } from '../pages/employer/JobEditorPage'
import { TalentDetailPage } from '../pages/employer/TalentDetailPage'
import { TalentSearchPage } from '../pages/employer/TalentSearchPage'
import { ForgotPasswordPage } from '../pages/ForgotPasswordPage'
import { EmployerPublicPage } from '../pages/jobs/EmployerPublicPage'
import { JobDetailPage } from '../pages/jobs/JobDetailPage'
import { JobsPage } from '../pages/jobs/JobsPage'
import { MyApplicationsPage } from '../pages/jobs/MyApplicationsPage'
import { SeekerProfilePage } from '../pages/jobs/SeekerProfilePage'
import { HomePage } from '../pages/HomePage'
import { LoginPage } from '../pages/LoginPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { ProfilePage } from '../pages/ProfilePage'
import { ProviderDetailPage } from '../pages/providers/ProviderDetailPage'
import { ProviderProfilePage } from '../pages/providers/ProviderProfilePage'
import { ProviderOffersPage } from '../pages/offers/ProviderOffersPage'
import { AdvertisingWorkspacePage } from '../pages/advertising/AdvertisingWorkspacePage'
import { CompanyWorkspacePage } from '../pages/marketplace/CompanyWorkspacePage'
import { MarketplacePage } from '../pages/marketplace/MarketplacePage'
import { ProductDetailPage } from '../pages/marketplace/ProductDetailPage'
import { OwnerWorkspacePage } from '../pages/realEstate/OwnerWorkspacePage'
import { RealEstateDetailPage } from '../pages/realEstate/RealEstateDetailPage'
import { RealEstatePage } from '../pages/realEstate/RealEstatePage'
import { MyReservationsPage } from '../pages/reservations/MyReservationsPage'
import { ProviderReservationsPage } from '../pages/reservations/ProviderReservationsPage'
import { ProvidersPage } from '../pages/providers/ProvidersPage'
import { RegisterPage } from '../pages/RegisterPage'
import { ResetPasswordPage } from '../pages/ResetPasswordPage'
import { VerifyEmailPage } from '../pages/VerifyEmailPage'

/**
 * Route table. Three groups:
 *  - public:        reachable by everyone
 *  - PublicOnly:    login/register — authenticated users are redirected away
 *  - RequireAuth:   protected — add new authenticated pages under this element
 *  - RequireStaff:  staff-only control plane (account.is_staff)
 */
export const routes: RouteObject[] = [
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'providers', element: <ProvidersPage /> },
      { path: 'providers/:id', element: <ProviderDetailPage /> },
      { path: 'jobs', element: <JobsPage /> },
      { path: 'jobs/:id', element: <JobDetailPage /> },
      { path: 'employers/:id', element: <EmployerPublicPage /> },
      // Medical real estate is publicly browsable; the backend decides what is visible.
      { path: 'real-estate', element: <RealEstatePage /> },
      { path: 'real-estate/:id', element: <RealEstateDetailPage /> },
      { path: 'forgot-password', element: <ForgotPasswordPage /> },
      { path: 'reset-password', element: <ResetPasswordPage /> },
      { path: 'verify-email', element: <VerifyEmailPage /> },
      {
        element: <PublicOnly />,
        children: [
          { path: 'login', element: <LoginPage /> },
          { path: 'register', element: <RegisterPage /> },
        ],
      },
      {
        element: <RequireAuth />,
        children: [
          { path: 'profile', element: <ProfilePage /> },
          {
            element: <RequireRole roles={['PATIENT']} />,
            children: [{ path: 'reservations', element: <MyReservationsPage /> }],
          },
          { path: 'jobs/profile', element: <SeekerProfilePage /> },
          { path: 'jobs/my-applications', element: <MyApplicationsPage /> },
          { path: 'employer', element: <EmployerWorkspacePage /> },
          { path: 'employer/jobs/new', element: <JobEditorPage /> },
          { path: 'employer/jobs/:id', element: <JobEditorPage /> },
          { path: 'employer/jobs/:id/applications', element: <ApplicantsPage /> },
          { path: 'employer/talent', element: <TalentSearchPage /> },
          { path: 'employer/talent/:id', element: <TalentDetailPage /> },
          {
            element: <RequireStaff />,
            children: [{ path: 'admin-console', element: <AdminConsolePage /> }],
          },
          {
            element: <RequireRole roles={['PROVIDER']} />,
            children: [
              { path: 'provider/profile', element: <ProviderProfilePage /> },
              { path: 'provider/reservations', element: <ProviderReservationsPage /> },
              { path: 'provider/offers', element: <ProviderOffersPage /> },
              // B2B catalogue: the backend decides which products this provider may see.
              { path: 'marketplace', element: <MarketplacePage /> },
              { path: 'marketplace/products/:id', element: <ProductDetailPage /> },
            ],
          },
          {
            element: <RequireRole roles={['MEDICAL_COMPANY']} deniedTitleKey="company.notCompany" />,
            children: [
              { path: 'company', element: <CompanyWorkspacePage /> },
              { path: 'company/advertising', element: <AdvertisingWorkspacePage /> },
            ],
          },
          {
            element: <RequireRole roles={['REAL_ESTATE_SELLER']} deniedTitleKey="realEstateOwner.notSeller" />,
            children: [{ path: 'real-estate/owner', element: <OwnerWorkspacePage /> }],
          },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
