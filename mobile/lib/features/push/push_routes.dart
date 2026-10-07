import '../auth/data/auth_models.dart';
import '../notifications/data/notification_models.dart';

/// The one place that turns backend notification / push data into an in-app route. It only knows
/// the codes the backend actually defines (`NotificationEventType`, `NotificationResourceType`,
/// the push `type` values), validates every id as a UUID before using it in a path, and returns
/// null for anything else — so an unknown or malformed value is shown but never navigated. The
/// resulting screen still applies its own capability gate and the backend still authorizes the
/// request: a route is never a grant.
const notificationsRoute = '/notifications';
const chatRoute = '/chat';

final RegExp _uuid = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
);

bool isValidId(String? value) => value != null && _uuid.hasMatch(value);

const _knownEvents = {'RESERVATION_CREATED', 'RESERVATION_STATUS_CHANGED'};

const _providerReservationCapability = 'reservations.manage_received';
const _patientReservationCapability = 'reservations.create_own';

/// Where tapping a notification row goes, for [account]; null = nothing to open.
String? routeForNotification(AppNotification notification, Account account) {
  if (!_knownEvents.contains(notification.eventType)) return null;
  if (notification.resourceType != 'RESERVATION') return null;
  final id = notification.resourceId;
  if (!isValidId(id)) return null;
  // The same event goes to both participants; the account's capability picks its own side.
  if (account.hasPermission(_providerReservationCapability)) {
    return '/workspace/reservations/$id';
  }
  if (account.hasPermission(_patientReservationCapability)) {
    return '/reservations/$id';
  }
  return null;
}

/// Where a tapped push goes. The push carries no resource id (only `notification_id` /
/// `conversation_id`), so a notification push opens the notification centre (which fetches the
/// authoritative list) and a chat push opens that conversation (a 404 for anyone else).
String? routeForPush(Map<String, String> data) {
  switch (data['type']) {
    case 'notification':
      return isValidId(data['notification_id']) ? notificationsRoute : null;
    case 'chat_message':
      final id = data['conversation_id'];
      return isValidId(id) ? '$chatRoute/$id' : null;
  }
  return null;
}
