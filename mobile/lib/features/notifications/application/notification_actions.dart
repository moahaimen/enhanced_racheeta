import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/account_scope.dart';
import '../data/notification_models.dart';
import 'notifications_providers.dart';

/// After a read mutation the list and the count are reloaded from the backend (never patched
/// locally, so they cannot drift from the server's state).
void refreshNotifications(WidgetRef ref) {
  ref
    ..invalidate(notificationsProvider)
    ..invalidate(notificationUnreadProvider);
}

/// `POST /notifications/{id}/read/`: one request for the initiating account only (see
/// `runAsAccount`); a result that arrives under another account is dropped.
Future<AppNotification> markNotificationRead(WidgetRef ref, String id) =>
    runAsAccount(
      ref,
      () => ref.read(notificationsApiProvider).markRead(id),
      () => refreshNotifications(ref),
    );

/// `POST /notifications/read-all/`.
Future<int> markAllNotificationsRead(WidgetRef ref) => runAsAccount(
  ref,
  () => ref.read(notificationsApiProvider).markAllRead(),
  () => refreshNotifications(ref),
);
