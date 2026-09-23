import type { RouteObject } from 'react-router'

import { AppLayout } from './AppLayout'
import { PublicOnly, RequireAuth, RequireRole } from './guards'
import { ForgotPasswordPage } from '../pages/ForgotPasswordPage'
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
 */
export const routes: RouteObject[] = [
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'providers', element: <ProvidersPage /> },
      { path: 'providers/:id', element: <ProviderDetailPage /> },
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
            element: <RequireRole roles={['PROVIDER']} />,
            children: [{ path: 'provider/profile', element: <ProviderProfilePage /> }],
          },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
