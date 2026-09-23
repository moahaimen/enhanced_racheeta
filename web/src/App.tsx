import { createBrowserRouter, RouterProvider } from 'react-router'

import { routes } from './app/routes'
import { AuthProvider } from './auth/AuthContext'

const router = createBrowserRouter(routes)

export default function App() {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  )
}
