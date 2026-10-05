import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../l10n/generated/app_localizations.dart';
import '../../shared/theme/app_theme.dart';
import '../auth/application/account_scope.dart';
import '../auth/data/auth_models.dart';
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
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push(entry.path),
            ),
          ),
      ],
    );
  }
}
