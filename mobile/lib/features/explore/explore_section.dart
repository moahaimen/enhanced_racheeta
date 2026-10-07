import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../l10n/generated/app_localizations.dart';
import '../../shared/theme/app_theme.dart';
import '../auth/application/account_scope.dart';
import '../auth/data/auth_models.dart';
import '../chat/application/chat_providers.dart';
import '../notifications/application/notifications_providers.dart';
import 'dashboard_index_provider.dart';
import 'explore_entries.dart';

/// The *Explore* list on Home: the extra areas this account may open.
class ExploreSection extends ConsumerWidget {
  const ExploreSection({required this.account, super.key});
  final Account account;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final dashboards =
        ref.watch(dashboardIndexProvider(ref.watch(accountIdProvider))).value ??
        const <String>{};
    final entries = exploreFor(account, dashboards);
    final accountId = ref.watch(accountIdProvider);
    // Backend-authoritative counts, keyed by account (another account's count is never shown
    // while this one loads). Errors simply show no badge.
    int unread(UnreadKind? kind) => switch (kind) {
      UnreadKind.notifications =>
        ref.watch(notificationUnreadProvider(accountId)).value ?? 0,
      UnreadKind.chat => ref.watch(chatUnreadProvider(accountId)).value ?? 0,
      null => 0,
    };
    if (entries.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: RacheetaSpacing.xl),
        Semantics(
          header: true,
          child: Text(
            l10n.exploreTitle,
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        const SizedBox(height: RacheetaSpacing.sm),
        for (final entry in entries)
          Card(
            key: Key('explore-${entry.id}'),
            margin: const EdgeInsets.only(bottom: RacheetaSpacing.sm),
            child: ListTile(
              minTileHeight: RacheetaSpacing.minTouchTarget,
              leading: Icon(entry.icon),
              title: Text(entry.label(l10n)),
              trailing: _trailing(entry, unread(entry.unreadKind), l10n),
              onTap: () => context.push(entry.path),
            ),
          ),
      ],
    );
  }
}

Widget _trailing(ExploreEntry entry, int unread, AppLocalizations l10n) {
  if (unread <= 0) return const Icon(Icons.chevron_right);
  return Semantics(
    label: l10n.notificationsUnreadCount(unread),
    child: Badge(
      key: Key('explore-unread-${entry.id}'),
      label: Text('$unread'),
    ),
  );
}
