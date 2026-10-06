import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/labels.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/account_scope.dart';
import '../application/marketplace_providers.dart';
import '../data/marketplace_models.dart';
import 'company_gate.dart';
import 'marketplace_errors.dart';

/// The medical company's home: the backend's own counts and the way to the company's products.
class CompanyWorkspacePage extends ConsumerWidget {
  const CompanyWorkspacePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return CompanyGate(
      title: l10n.companyWorkspaceTitle,
      child: const _Dashboard(),
    );
  }
}

class _Dashboard extends ConsumerWidget {
  const _Dashboard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final provider = companyDashboardProvider(ref.watch(accountIdProvider));
    final dashboard = ref.watch(provider);

    // Keyed by account: a value here always belongs to the signed-in account.
    if (dashboard.isLoading && !dashboard.hasValue) {
      return AppScaffold(
        title: l10n.companyWorkspaceTitle,
        body: const LoadingView(),
      );
    }
    if (dashboard.hasError && !dashboard.hasValue) {
      final error = dashboard.error;
      return AppScaffold(
        title: l10n.companyWorkspaceTitle,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? marketplaceErrorMessage(
                  l10n,
                  error,
                  MarketplaceAction.companyLoad,
                )
              : l10n.errorUnknown,
          onRetry: () async => ref.invalidate(provider),
        ),
      );
    }
    final data = dashboard.requireValue;
    return AppScaffold(
      title: l10n.companyWorkspaceTitle,
      scrollable: false,
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(provider);
          try {
            await ref.read(provider.future);
          } on Object {
            // the error view reports it
          }
        },
        child: ListView(
          children: [
            _Counts(data: data),
            const SizedBox(height: RacheetaSpacing.lg),
            PrimaryButton(
              key: const Key('open-company-products'),
              label: l10n.companyProductsTitle,
              icon: Icons.inventory_2_outlined,
              onPressed: () async => context.push('/company/products'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Counts extends StatelessWidget {
  const _Counts({required this.data});
  final CompanyDashboard data;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    Widget stat(String label, String value) => Padding(
      padding: const EdgeInsets.symmetric(vertical: RacheetaSpacing.xs),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          Text(value, style: Theme.of(context).textTheme.titleSmall),
        ],
      ),
    );
    return Card(
      key: const Key('company-counts'),
      child: Padding(
        padding: const EdgeInsets.all(RacheetaSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Semantics(
              header: true,
              child: Text(
                l10n.companyProductsTitle,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            const SizedBox(height: RacheetaSpacing.sm),
            stat(
              l10n.dashboardVerification,
              verificationLabel(l10n, data.verificationStatus),
            ),
            Padding(
              padding: const EdgeInsets.only(bottom: RacheetaSpacing.sm),
              child: Text(
                data.canPublish
                    ? l10n.companyCanPublish
                    : l10n.companyCannotPublish,
                key: const Key('company-can-publish'),
              ),
            ),
            const Divider(),
            stat(l10n.productsTotal, '${data.total}'),
            stat(l10n.productsActive, '${data.active}'),
            stat(l10n.productsInactive, '${data.inactive}'),
            stat(l10n.productsExposable, '${data.exposable}'),
          ],
        ),
      ),
    );
  }
}
