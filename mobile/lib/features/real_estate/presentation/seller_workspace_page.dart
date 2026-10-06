import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/account_scope.dart';
import '../application/real_estate_providers.dart';
import '../data/real_estate_models.dart';
import 'real_estate_errors.dart';
import 'seller_gate.dart';

/// The property owner's home: the backend's own counts and the way to the owner's listings.
class SellerWorkspacePage extends ConsumerWidget {
  const SellerWorkspacePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return SellerGate(
      title: l10n.sellerWorkspaceTitle,
      child: const _Dashboard(),
    );
  }
}

class _Dashboard extends ConsumerWidget {
  const _Dashboard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final provider = ownerDashboardProvider(ref.watch(accountIdProvider));
    final dashboard = ref.watch(provider);

    // Keyed by account: a value here always belongs to the signed-in account.
    if (dashboard.isLoading && !dashboard.hasValue) {
      return AppScaffold(
        title: l10n.sellerWorkspaceTitle,
        body: const LoadingView(),
      );
    }
    if (dashboard.hasError && !dashboard.hasValue) {
      final error = dashboard.error;
      return AppScaffold(
        title: l10n.sellerWorkspaceTitle,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? realEstateErrorMessage(l10n, error, RealEstateAction.load)
              : l10n.errorUnknown,
          onRetry: () async => ref.invalidate(provider),
        ),
      );
    }
    final data = dashboard.requireValue;
    return AppScaffold(
      title: l10n.sellerWorkspaceTitle,
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
              key: const Key('open-owner-listings'),
              label: l10n.ownerListingsTitle,
              icon: Icons.apartment,
              onPressed: () async => context.push('/seller/listings'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Counts extends StatelessWidget {
  const _Counts({required this.data});
  final OwnerDashboard data;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    Widget stat(String label, int value) => Padding(
      padding: const EdgeInsets.symmetric(vertical: RacheetaSpacing.xs),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          Text('$value', style: Theme.of(context).textTheme.titleSmall),
        ],
      ),
    );
    return Card(
      key: const Key('seller-counts'),
      child: Padding(
        padding: const EdgeInsets.all(RacheetaSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Semantics(
              header: true,
              child: Text(
                l10n.ownerListingsTitle,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            const SizedBox(height: RacheetaSpacing.sm),
            stat(l10n.sellerListingsTotal, data.total),
            stat(l10n.sellerDraft, data.draft),
            stat(l10n.sellerPublished, data.published),
            stat(l10n.sellerVisible, data.visible),
            stat(l10n.sellerExpired, data.expired),
            const Divider(),
            stat(l10n.transactionSale, data.sale),
            stat(l10n.transactionRent, data.rent),
          ],
        ),
      ),
    );
  }
}
