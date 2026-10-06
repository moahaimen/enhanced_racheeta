import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/search/search_query.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/paged_list.dart';
import '../../../shared/widgets/search_filter_bar.dart';
import '../../../shared/theme/app_theme.dart';
import '../../discovery/application/discovery_providers.dart';
import '../../auth/application/account_scope.dart';
import '../application/real_estate_providers.dart';
import '../data/real_estate_api.dart';
import 'listing_tile.dart';
import 'real_estate_errors.dart';
import 'real_estate_labels.dart';

/// The public medical real-estate catalogue: backend search, filters and ordering, paginated.
class RealEstatePage extends ConsumerWidget {
  const RealEstatePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final query = ref.watch(listingQueryProvider);
    final results = ref.watch(listingsProvider);
    final controller = ref.read(listingsProvider.notifier);
    return AppScaffold(
      title: l10n.realEstateTitle,
      scrollable: false,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SearchFilterBar(
            scopeKey: ref.watch(accountIdProvider),
            query: query,
            searchLabel: l10n.realEstateSearchHint,
            filtersTitle: l10n.realEstateFiltersTitle,
            onChanged: ref.read(listingQueryProvider.notifier).update,
            fieldsBuilder: (ref, l10n) {
              final governorates = ref.watch(governoratesProvider);
              final language = Localizations.localeOf(ref.context).languageCode;
              return [
                FilterField(
                  key: ListingFilterKeys.transaction,
                  label: l10n.filterTransaction,
                  options: [
                    for (final code in transactionCodes)
                      FilterOption(code, transactionLabel(l10n, code)),
                  ],
                ),
                FilterField(
                  key: ListingFilterKeys.propertyType,
                  label: l10n.filterPropertyType,
                  options: [
                    for (final code in propertyTypeCodes)
                      FilterOption(code, propertyTypeLabel(l10n, code)),
                  ],
                ),
                FilterField(
                  key: ListingFilterKeys.governorate,
                  label: l10n.filterGovernorate,
                  failed: governorates.hasError,
                  options: governorates.value
                      ?.map((p) => FilterOption(p.id, p.name(language)))
                      .toList(),
                ),
                FilterField(
                  key: ListingFilterKeys.ordering,
                  label: l10n.sortLabel,
                  options: [
                    FilterOption('price', l10n.sortPriceAsc),
                    FilterOption('-price', l10n.sortPriceDesc),
                  ],
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
              errorMessage: (l10n, error) =>
                  realEstateErrorMessage(l10n, error, RealEstateAction.load),
              emptyIcon: Icons.apartment,
              emptyTitle: l10n.realEstateEmptyTitle,
              emptyMessage: l10n.discoverEmptyBody,
              emptyAction: query.isEmpty
                  ? null
                  : SecondaryButton(
                      label: l10n.clearFilters,
                      onPressed: () async => ref
                          .read(listingQueryProvider.notifier)
                          .update(const SearchQuery()),
                    ),
              itemBuilder: (context, listing) => ListingTile(
                listing: listing,
                onTap: () => context.push('/real-estate/listing/${listing.id}'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
