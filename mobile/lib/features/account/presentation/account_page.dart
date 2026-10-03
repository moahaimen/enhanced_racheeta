import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/confirm_dialog.dart';
import '../../auth/application/providers.dart';
import '../../auth/application/session_state.dart';
import '../../auth/presentation/language_switcher.dart';
import '../role_label.dart';

/// Read-only account details (from `/me`), language, and sign-out.
class AccountPage extends ConsumerWidget {
  const AccountPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final session = ref.watch(sessionControllerProvider);
    if (session is! SessionAuthenticated) return const SizedBox.shrink();
    final account = session.account;

    Future<bool> confirmLogout() => showConfirmDialog(
      context,
      title: l10n.logoutConfirmTitle,
      message: l10n.logoutConfirmBody,
      confirmLabel: l10n.logout,
    );
    Future<void> logout() =>
        ref.read(sessionControllerProvider.notifier).logout();

    return AppScaffold(
      title: l10n.accountTitle,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: RacheetaSpacing.sm),
              child: Column(
                children: [
                  _Row(
                    l10n.accountName,
                    account.fullName,
                    valueKey: 'account-name',
                  ),
                  _Row(
                    l10n.accountEmail,
                    account.email,
                    valueKey: 'account-email',
                    ltr: true,
                  ),
                  _Row(
                    l10n.accountPhone,
                    account.phoneNumber.isEmpty
                        ? l10n.accountNotProvided
                        : account.phoneNumber,
                    ltr: account.phoneNumber.isNotEmpty,
                  ),
                  _Row(
                    l10n.accountRole,
                    roleLabel(l10n, account.roleCode),
                    valueKey: 'account-role',
                  ),
                  _Row(
                    l10n.accountEmailStatus,
                    account.emailVerified
                        ? l10n.accountEmailVerified
                        : l10n.accountEmailNotVerified,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: RacheetaSpacing.lg),
          Card(
            child: ListTile(
              title: Text(l10n.accountLanguage),
              trailing: const LanguageSwitcher(),
            ),
          ),
          const SizedBox(height: RacheetaSpacing.xl),
          SecondaryButton(
            label: l10n.logout,
            pendingLabel: l10n.loggingOut,
            icon: Icons.logout,
            confirm: confirmLogout,
            onPressed: logout,
          ),
        ],
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row(this.label, this.value, {this.valueKey, this.ltr = false});
  final String label;
  final String value;
  final String? valueKey;
  final bool ltr;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: RacheetaSpacing.lg,
        vertical: RacheetaSpacing.sm,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            flex: 2,
            child: Text(
              label,
              style: TextStyle(color: theme.colorScheme.onSurfaceVariant),
            ),
          ),
          Expanded(
            flex: 3,
            child: Text(
              value,
              key: valueKey == null ? null : Key(valueKey!),
              textDirection: ltr ? TextDirection.ltr : null,
              textAlign: TextAlign.start,
            ),
          ),
        ],
      ),
    );
  }
}
