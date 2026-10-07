import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/page.dart';
import '../../../core/paging/paged_notifier.dart';
import '../../auth/application/account_scope.dart';
import '../../auth/application/providers.dart';
import '../data/notification_models.dart';
import '../data/notifications_api.dart';

final Provider<NotificationsApi> notificationsApiProvider =
    Provider<NotificationsApi>(
      (ref) => NotificationsApi(ref.watch(apiClientProvider)),
    );

/// The signed-in account's persistent notifications (newest first, as the backend orders them).
/// Rebuilt — requests cancelled, late answers dropped — whenever the account changes.
class NotificationsController extends PagedNotifier<AppNotification> {
  @override
  PagedState<AppNotification> build() {
    ref.watch(accountIdProvider);
    return start();
  }

  @override
  Future<Page<AppNotification>> fetchPage(int page, CancelToken token) => ref
      .read(notificationsApiProvider)
      .notifications(
        page: page,
        pageSize: PagedNotifier.pageSize,
        cancelToken: token,
      );
}

final notificationsProvider =
    NotifierProvider<NotificationsController, PagedState<AppNotification>>(
      NotificationsController.new,
      retry: noRetry,
    );

/// The authoritative unread count, keyed by the account: another account's count is never shown
/// while this one loads. Refreshed (invalidated) after a mark-read and after a foreground push.
final notificationUnreadProvider = FutureProvider.autoDispose
    .family<int, String?>((ref, accountId) {
      if (accountId == null) return 0;
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      return ref
          .watch(notificationsApiProvider)
          .unreadCount(cancelToken: token);
    }, retry: noRetry);
