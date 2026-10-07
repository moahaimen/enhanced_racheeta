import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/time/time_providers.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/paged_list.dart';
import '../../auth/application/account_scope.dart';
import '../../auth/application/providers.dart';
import '../../auth/application/session_state.dart';
import '../../push/push_registration.dart';
import '../../push/push_routes.dart';
import '../../push/push_source.dart';
import '../application/notification_actions.dart';
import '../application/notifications_providers.dart';
import '../data/notification_models.dart';
import 'communication_errors.dart';

/// The persistent notification centre. Everything shown is the backend's own state: the list, the
/// unread count and the read flags are reloaded after every mutation, never patched locally.
class NotificationsPage extends ConsumerStatefulWidget {
  const NotificationsPage({super.key});

  @override
  ConsumerState<NotificationsPage> createState() => _NotificationsPageState();
}

class _NotificationsPageState extends ConsumerState<NotificationsPage> {
  String? _message;
  bool _isError = false;
  final Set<String> _marking = <String>{};
  bool _markAllBusy = false;

  /// Messages and in-flight marks belong to one account.
  void _resetForAccountChange() => setState(() {
    _message = null;
    _isError = false;
    _marking.clear();
    _markAllBusy = false;
  });

  Future<void> _open(AppNotification notification) async {
    final l10n = AppLocalizations.of(context);
    final session = ref.read(sessionControllerProvider);
    final route = session is SessionAuthenticated
        ? routeForNotification(notification, session.account)
        : null;
    final accountId = ref.read(accountIdProvider);
    if (!notification.isRead && _marking.add(notification.id)) {
      setState(() => _message = null);
      unawaited(_mark(notification.id, accountId, l10n));
    }
    if (route != null) await context.push(route);
  }

  Future<void> _mark(
    String id,
    String? accountId,
    AppLocalizations l10n,
  ) async {
    try {
      await markNotificationRead(ref, id);
    } on StaleSessionException {
      return; // another account is signed in: nothing of A's may show
    } on ApiException {
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _message = l10n.errorNotificationMark;
        _isError = true;
      });
    } finally {
      if (mounted && ref.read(accountIdProvider) == accountId) {
        setState(() => _marking.remove(id));
      }
    }
  }

  Future<void> _markAll() async {
    if (_markAllBusy) return; // one request per deliberate action
    final l10n = AppLocalizations.of(context);
    final accountId = ref.read(accountIdProvider);
    setState(() {
      _markAllBusy = true;
      _message = null;
    });
    try {
      final updated = await markAllNotificationsRead(ref);
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _message = l10n.notificationsAllMarked(updated);
        _isError = false;
      });
    } on StaleSessionException {
      // another account is signed in: nothing of A's may show
    } on ApiException {
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _message = l10n.errorNotificationMark;
        _isError = true;
      });
    } finally {
      // Only the account that started it may clear its busy flag (B's was reset on the switch).
      if (mounted && ref.read(accountIdProvider) == accountId) {
        setState(() => _markAllBusy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final theme = Theme.of(context);
    ref.listen<String?>(accountIdProvider, (previous, next) {
      if (previous != next) _resetForAccountChange();
    });
    final accountId = ref.watch(accountIdProvider);
    final wallClock = ref.watch(wallClockProvider);
    final state = ref.watch(notificationsProvider);
    final controller = ref.read(notificationsProvider.notifier);
    final unread = ref.watch(notificationUnreadProvider(accountId));
    final push = ref.watch(pushRegistrationProvider);
    final pushAvailable = ref.watch(pushSourceProvider).isAvailable;

    return AppScaffold(
      title: l10n.notificationsTitle,
      scrollable: false,
      body: PagedListView<AppNotification>(
        state: state,
        onLoadMore: controller.loadMore,
        onReload: () {
          controller.reload();
          ref.invalidate(notificationUnreadProvider);
        },
        errorMessage: communicationErrorMessage,
        emptyIcon: Icons.notifications_none,
        emptyTitle: l10n.notificationsEmpty,
        emptyMessage: l10n.notificationsEmptyBody,
        showCount: false,
        header: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (pushAvailable &&
                push.permission == PushPermission.notDetermined)
              Card(
                key: const Key('push-prompt'),
                child: Padding(
                  padding: const EdgeInsets.all(RacheetaSpacing.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        l10n.pushPromptTitle,
                        style: theme.textTheme.titleSmall,
                      ),
                      const SizedBox(height: RacheetaSpacing.xs),
                      Text(l10n.pushPromptBody),
                      const SizedBox(height: RacheetaSpacing.sm),
                      SecondaryButton(
                        key: const Key('push-allow'),
                        label: l10n.pushPromptAction,
                        icon: Icons.notifications_active_outlined,
                        onPressed: () => ref
                            .read(pushRegistrationProvider.notifier)
                            .requestPermission(),
                      ),
                    ],
                  ),
                ),
              )
            else if (pushAvailable && push.permission == PushPermission.denied)
              Padding(
                padding: const EdgeInsets.only(bottom: RacheetaSpacing.md),
                child: Text(
                  l10n.pushDeniedHint,
                  key: const Key('push-denied'),
                  style: theme.textTheme.bodySmall,
                ),
              ),
            if (_message != null)
              Padding(
                padding: const EdgeInsets.only(bottom: RacheetaSpacing.md),
                child: Semantics(
                  liveRegion: true,
                  child: Text(
                    _message!,
                    key: const Key('notifications-message'),
                    style: TextStyle(
                      color: _isError
                          ? theme.colorScheme.error
                          : RacheetaColors.success,
                    ),
                  ),
                ),
              ),
            // A Wrap, not a Row: at large text sizes the count and the action flow onto two lines
            // instead of one squeezing the other off screen.
            Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Padding(
                  padding: const EdgeInsetsDirectional.only(
                    end: RacheetaSpacing.md,
                  ),
                  child: Text(
                    unread.hasValue
                        ? l10n.notificationsUnreadCount(unread.requireValue)
                        : '',
                    key: const Key('notifications-unread'),
                    style: theme.textTheme.bodySmall,
                  ),
                ),
                // A request pending for the previous account must not leave this account's
                // button disabled: a new account gets a fresh button.
                KeyedSubtree(
                  key: ValueKey(accountId),
                  child: TextButton.icon(
                    key: const Key('notifications-mark-all'),
                    icon: const Icon(Icons.done_all),
                    label: Text(
                      _markAllBusy
                          ? l10n.notificationsMarkingAll
                          : l10n.notificationsMarkAll,
                    ),
                    onPressed: ((unread.value ?? 1) == 0 || _markAllBusy)
                        ? null
                        : _markAll,
                  ),
                ),
              ],
            ),
          ],
        ),
        itemBuilder: (context, notification) => _NotificationTile(
          notification: notification,
          time: formatDateTime(notification.createdAt, wallClock, locale),
          onTap: () => _open(notification),
        ),
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({
    required this.notification,
    required this.time,
    required this.onTap,
  });
  final AppNotification notification;
  final String time;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final unread = !notification.isRead;
    final title = notification.title.isEmpty
        ? l10n.notificationFallbackTitle
        : notification.title;
    return Card(
      key: Key('notification-${notification.id}'),
      margin: const EdgeInsets.only(bottom: RacheetaSpacing.sm),
      color: unread ? theme.colorScheme.primaryContainer : null,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(RacheetaSpacing.lg),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Semantics(
                label: unread ? l10n.notificationUnread : l10n.notificationRead,
                child: Icon(
                  unread ? Icons.circle : Icons.circle_outlined,
                  size: 12,
                  key: Key(
                    unread
                        ? 'unread-${notification.id}'
                        : 'read-${notification.id}',
                  ),
                ),
              ),
              const SizedBox(width: RacheetaSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: unread ? FontWeight.w700 : FontWeight.w500,
                      ),
                    ),
                    if (notification.body.isNotEmpty) Text(notification.body),
                    const SizedBox(height: RacheetaSpacing.xs),
                    Text(time, style: theme.textTheme.bodySmall),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
