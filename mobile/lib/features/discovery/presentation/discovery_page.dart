import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/error_messages.dart';
import '../../../core/paging/paged_notifier.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/states.dart';
import '../application/discovery_providers.dart';
import '../data/discovery_api.dart';
import '../data/discovery_models.dart';
import 'filters_sheet.dart';
import 'provider_card_tile.dart';

/// Patient provider discovery: search, filters, paginated results.
class DiscoveryPage extends ConsumerStatefulWidget {
  const DiscoveryPage({super.key});

  @override
  ConsumerState<DiscoveryPage> createState() => _DiscoveryPageState();
}

class _DiscoveryPageState extends ConsumerState<DiscoveryPage> {
  static const _debounce = Duration(milliseconds: 400);
  late final TextEditingController _search = TextEditingController(
    text: ref.read(discoveryFiltersProvider).search,
  );
  Timer? _timer;

  @override
  void dispose() {
    _timer?.cancel();
    _search.dispose();
    super.dispose();
  }

  void _applySearch(String text) {
    _timer?.cancel();
    final filters = ref.read(discoveryFiltersProvider);
    if (filters.search == text) return;
    ref
        .read(discoveryFiltersProvider.notifier)
        .update(filters.copyWith(search: text));
  }

  void _onChanged(String text) {
    setState(() {}); // clear button visibility
    _timer?.cancel();
    _timer = Timer(_debounce, () => _applySearch(text));
  }

  Future<void> _openFilters() async {
    final current = ref.read(discoveryFiltersProvider);
    final result = await showFiltersSheet(context, current);
    if (result != null && mounted) {
      ref.read(discoveryFiltersProvider.notifier).update(result);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final filters = ref.watch(discoveryFiltersProvider);
    final results = ref.watch(providerSearchProvider);
    final activeFilters = filters.activeFilterCount;

    return AppScaffold(
      title: l10n.discoverTitle,
      scrollable: false,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _search,
                  textInputAction: TextInputAction.search,
                  onChanged: _onChanged,
                  onSubmitted: _applySearch,
                  decoration: InputDecoration(
                    labelText: l10n.searchHint,
                    prefixIcon: const Icon(Icons.search),
                    suffixIcon: _search.text.isEmpty
                        ? null
                        : IconButton(
                            tooltip: l10n.searchClear,
                            icon: const Icon(Icons.close),
                            onPressed: () {
                              _search.clear();
                              _applySearch('');
                              setState(() {});
                            },
                          ),
                  ),
                ),
              ),
              const SizedBox(width: RacheetaSpacing.sm),
              Badge(
                isLabelVisible: activeFilters > 0,
                label: Text('$activeFilters'),
                child: IconButton.filledTonal(
                  tooltip: l10n.filtersButton,
                  icon: const Icon(Icons.tune),
                  onPressed: _openFilters,
                ),
              ),
            ],
          ),
          const SizedBox(height: RacheetaSpacing.md),
          Expanded(
            child: _Results(
              state: results,
              filtersAreDefault: filters.isDefault,
            ),
          ),
        ],
      ),
    );
  }
}

class _Results extends ConsumerWidget {
  const _Results({required this.state, required this.filtersAreDefault});
  final PagedState<ProviderCard> state;
  final bool filtersAreDefault;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final controller = ref.read(providerSearchProvider.notifier);
    switch (state.phase) {
      case PagedPhase.loading:
        return const LoadingView();
      case PagedPhase.error:
        return ErrorView(
          message: apiErrorMessage(l10n, state.error!),
          onRetry: () async => controller.reload(),
        );
      case PagedPhase.ready:
        break;
    }
    final items = ref.watch(providerSearchProvider).items;
    if (items.isEmpty) {
      return Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          EmptyView(
            icon: Icons.search_off,
            title: l10n.discoverEmptyTitle,
            message: l10n.discoverEmptyBody,
          ),
          if (!filtersAreDefault)
            SecondaryButton(
              label: l10n.clearFilters,
              onPressed: () async {
                final current = ref.read(discoveryFiltersProvider);
                ref
                    .read(discoveryFiltersProvider.notifier)
                    .update(DiscoveryFilters(search: current.search));
              },
            ),
        ],
      );
    }
    return RefreshIndicator(
      onRefresh: () async => controller.reload(),
      child: ListView.builder(
        itemCount: items.length + 2,
        itemBuilder: (context, index) {
          if (index == 0) {
            return Padding(
              padding: const EdgeInsets.only(bottom: RacheetaSpacing.sm),
              child: Text(
                l10n.resultsCount(state.count),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            );
          }
          if (index == items.length + 1) {
            return _Footer(state: state, onLoadMore: controller.loadMore);
          }
          final card = items[index - 1];
          return ProviderCardTile(
            card: card,
            onTap: () => context.push('/providers/${card.id}'),
          );
        },
      ),
    );
  }
}

class _Footer extends StatelessWidget {
  const _Footer({required this.state, required this.onLoadMore});
  final PagedState<ProviderCard> state;
  final Future<void> Function() onLoadMore;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    if (!state.hasMore) return const SizedBox(height: RacheetaSpacing.lg);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: RacheetaSpacing.md),
      child: Column(
        children: [
          if (state.loadMoreError != null)
            Padding(
              padding: const EdgeInsets.only(bottom: RacheetaSpacing.sm),
              child: Text(
                l10n.loadMoreFailed,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          if (state.loadingMore)
            const CircularProgressIndicator()
          else
            SecondaryButton(label: l10n.loadMore, onPressed: onLoadMore),
        ],
      ),
    );
  }
}
