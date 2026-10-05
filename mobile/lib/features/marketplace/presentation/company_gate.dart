import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/states.dart';
import '../application/marketplace_providers.dart';

/// Shows [child] only while the signed-in account's `/me` lists the company capability (watched
/// live, so a permission change, logout or account switch replaces the screen at once). The
/// backend still authorizes every call.
class CompanyGate extends ConsumerWidget {
  const CompanyGate({required this.title, required this.child, super.key});
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (ref.watch(canUseCompanyWorkspaceProvider)) return child;
    final l10n = AppLocalizations.of(context);
    return AppScaffold(
      title: title,
      scrollable: false,
      body: EmptyView(icon: Icons.lock_outline, title: l10n.companyOnly),
    );
  }
}
