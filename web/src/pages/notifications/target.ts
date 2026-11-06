import type { AppNotification } from '../../api'

/**
 * Where a notification leads, derived on the client from its resource and the viewer's
 * role. URLs are never stored. Unknown resources and roles get no link.
 */
export function notificationTarget(notification: AppNotification, role: string | undefined): string | null {
  if (notification.resource_type === 'INQUIRY') {
    // Received → the owner's inbox; answered → the asker's own list (whatever their role).
    return notification.event_type === 'INQUIRY_RECEIVED' ? '/real-estate/owner/inquiries' : '/real-estate/inquiries'
  }
  if (notification.resource_type === 'RESERVATION') {
    if (role === 'PATIENT') return '/reservations'
    if (role === 'PROVIDER') return '/provider/reservations'
  }
  return null
}
