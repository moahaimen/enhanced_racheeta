import { Outlet, useLocation } from 'react-router'

import { ChatProvider } from '../chat/ChatProvider'
import { useAuth } from '../auth/useAuth'
import { isWorkspacePath, SiteFooter, SiteHeader, WorkspaceSidebar } from '../design-system'
import { NotificationsProvider } from '../notifications/NotificationsProvider'
import styles from './AppLayout.module.css'

export function AppLayout() {
  const { pathname } = useLocation()
  const flush = pathname === '/'
  const { status } = useAuth()
  const workspace = status === 'authenticated' && isWorkspacePath(pathname)
  return (
    <NotificationsProvider>
      <ChatProvider>
        <div className={styles.shell}>
          <SiteHeader />
          <main className={`${styles.main} ${flush ? styles.mainFlush : ''}`.trim()}>
            {workspace ? (
              <div className={styles.workspace}>
                <WorkspaceSidebar />
                <div className={styles.workspaceMain}>
                  <Outlet />
                </div>
              </div>
            ) : (
              <Outlet />
            )}
          </main>
          <SiteFooter />
        </div>
      </ChatProvider>
    </NotificationsProvider>
  )
}
