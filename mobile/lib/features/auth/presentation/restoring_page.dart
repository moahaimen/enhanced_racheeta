import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/error_messages.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/widgets/states.dart';
import '../application/providers.dart';
import '../application/session_state.dart';

/// Shown while a stored session is validated, or when that could not be done (offline).
class RestoringPage extends ConsumerWidget {
  const RestoringPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final session = ref.watch(sessionControllerProvider);
    final controller = ref.read(sessionControllerProvider.notifier);
    return Scaffold(
      body: SafeArea(
        child: switch (session) {
          SessionRestoreFailed(:final error) => ErrorView(
            title: l10n.restoreFailedTitle,
            message:
                '${l10n.restoreFailedBody}\n${apiErrorMessage(l10n, error)}',
            onRetry: controller.restore,
            secondaryLabel: l10n.restoreUseAnotherAccount,
            onSecondary: controller.logout,
          ),
          _ => LoadingView(message: l10n.restoringTitle),
        },
      ),
    );
  }
}
