import { Outlet, useLocation } from 'react-router'

import { SiteFooter, SiteHeader } from '../design-system'
import styles from './AppLayout.module.css'

export function AppLayout() {
  const { pathname } = useLocation()
  const flush = pathname === '/'
  return (
    <div className={styles.shell}>
      <SiteHeader />
      <main className={`${styles.main} ${flush ? styles.mainFlush : ''}`.trim()}>
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  )
}
