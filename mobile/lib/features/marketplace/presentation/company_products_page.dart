import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/paged_list.dart';
import '../application/marketplace_providers.dart';
import 'company_gate.dart';
import 'marketplace_errors.dart';
import 'product_detail_page.dart';
import 'product_tile.dart';

/// The company's own products in the backend's order (newest first).
class CompanyProductsPage extends ConsumerWidget {
  const CompanyProductsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return CompanyGate(title: l10n.companyProductsTitle, child: const _List());
  }
}

class _List extends ConsumerWidget {
  const _List();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final state = ref.watch(companyProductsProvider);
    final controller = ref.read(companyProductsProvider.notifier);
    return AppScaffold(
      title: l10n.companyProductsTitle,
      scrollable: false,
      body: PagedListView(
        state: state,
        onLoadMore: controller.loadMore,
        onReload: controller.reload,
        errorMessage: (l10n, error) =>
            marketplaceErrorMessage(l10n, error, MarketplaceAction.companyLoad),
        emptyIcon: Icons.inventory_2_outlined,
        emptyTitle: l10n.companyProductsEmpty,
        emptyMessage: l10n.companyProductsEmptyBody,
        itemBuilder: (context, product) => ProductTile(
          product: product,
          badges: [
            Chip(
              label: Text(productStatusText(l10n, product.isActive)),
              visualDensity: VisualDensity.compact,
            ),
          ],
          onTap: () => context.push('/company/products/${product.id}'),
        ),
      ),
    );
  }
}
