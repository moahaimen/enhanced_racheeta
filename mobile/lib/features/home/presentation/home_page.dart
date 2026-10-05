import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../account/role_label.dart';
import '../../auth/application/providers.dart';
import '../../auth/application/session_state.dart';
import '../../auth/data/auth_models.dart';
import '../../explore/explore_section.dart';

/// Authenticated landing page: who is signed in (from `/me`) and the *Explore* entry points for
/// the extra areas this account may open (kept off the bottom bar so it stays small).
class HomePage extends ConsumerWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionControllerProvider);
    if (session is! SessionAuthenticated) return const SizedBox.shrink();
    final account = session.account;

    return AppScaffold(
      title: AppLocalizations.of(context).appName,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _Welcome(account: account),
          ExploreSection(account: account),
        ],
      ),
    );
  }
}

class _Welcome extends StatelessWidget {
  const _Welcome({required this.account});
  final Account account;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(RacheetaSpacing.xl),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Semantics(
              header: true,
              child: Text(
                l10n.homeGreeting(account.fullName),
                key: const Key('home-greeting'),
                style: theme.textTheme.headlineSmall,
              ),
            ),
            const SizedBox(height: RacheetaSpacing.sm),
            Text(
              l10n.homeSignedInAs(roleLabel(l10n, account.roleCode)),
              key: const Key('home-role'),
            ),
            if (!account.emailVerified) ...[
              const SizedBox(height: RacheetaSpacing.lg),
              Text(
                l10n.homeEmailNotVerified,
                style: TextStyle(color: theme.colorScheme.onSurfaceVariant),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
