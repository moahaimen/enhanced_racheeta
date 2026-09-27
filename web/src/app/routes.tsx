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
            children: [{ path: 'provider/profile', element: <ProviderProfilePage /> }],
          },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
