import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/search/search_query.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/paged_list.dart';
import '../../../shared/widgets/search_filter_bar.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/account_scope.dart';
import '../application/marketplace_providers.dart';
import '../data/marketplace_api.dart';
import 'marketplace_errors.dart';
import 'product_tile.dart';

/// The provider-facing medical marketplace: the products the backend targets at this provider,
/// optionally narrowed by category (the only filter the API documents).
class MarketplacePage extends ConsumerWidget {
  const MarketplacePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    if (!ref.watch(canBrowseMarketplaceProvider)) {
      return AppScaffold(
        title: l10n.marketplaceTitle,
        scrollable: false,
        body: EmptyView(
          icon: Icons.lock_outline,
          title: l10n.errorMarketplaceBrowse,
        ),
      );
    }
    final query = ref.watch(productQueryProvider);
    final results = ref.watch(productsProvider);
    final controller = ref.read(productsProvider.notifier);
    return AppScaffold(
      title: l10n.marketplaceTitle,
      scrollable: false,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SearchFilterBar(
            scopeKey: ref.watch(accountIdProvider),
            query: query,
            showSearch: false,
            filtersTitle: l10n.marketplaceFiltersTitle,
            onChanged: ref.read(productQueryProvider.notifier).update,
            fieldsBuilder: (ref, l10n) {
              final categories = ref.watch(categoriesProvider);
              final language = Localizations.localeOf(ref.context).languageCode;
              return [
                FilterField(
                  key: ProductFilterKeys.category,
                  label: l10n.marketplaceFilterCategory,
                  failed: categories.hasError,
                  options: categories.value
                      ?.map((c) => FilterOption(c.id, c.name(language)))
                      .toList(),
                ),
              ];
            },
          ),
          const SizedBox(height: RacheetaSpacing.md),
          Expanded(
            child: PagedListView(
              state: results,
              onLoadMore: controller.loadMore,
              onReload: controller.reload,
              errorMessage: (l10n, error) => marketplaceErrorMessage(
                l10n,
                error,
                MarketplaceAction.browse,
              ),
              emptyIcon: Icons.storefront_outlined,
              emptyTitle: l10n.marketplaceEmptyTitle,
              emptyMessage: l10n.marketplaceEmptyBody,
              emptyAction: query.isEmpty
                  ? null
                  : SecondaryButton(
                      label: l10n.clearFilters,
                      onPressed: () async => ref
                          .read(productQueryProvider.notifier)
                          .update(const SearchQuery()),
                    ),
              itemBuilder: (context, product) => ProductTile(
                product: product,
                onTap: () => context.push('/marketplace/product/${product.id}'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
