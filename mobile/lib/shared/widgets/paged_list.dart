import 'package:flutter/material.dart';

import '../../core/api/api_exception.dart';
import '../../core/paging/paged_notifier.dart';
import '../../l10n/generated/app_localizations.dart';
import '../theme/app_theme.dart';
import 'async_action_button.dart';
import 'states.dart';

/// The one list body for every paginated screen: loading, a safe error with retry, an explicit
/// empty state, the loaded items with a result count, and a "load more" footer that keeps the
/// items already shown when a later page fails. It only renders a [PagedState]; fetching, epochs
/// and stale-response protection live in `PagedNotifier`.
class PagedListView<T> extends StatelessWidget {
  const PagedListView({
    required this.state,
    required this.onLoadMore,
    required this.onReload,
    required this.itemBuilder,
    required this.errorMessage,
    required this.emptyTitle,
    this.emptyMessage,
    this.emptyIcon = Icons.inbox_outlined,
    this.emptyAction,
    this.header,
    this.showCount = true,
    super.key,
  });

  final PagedState<T> state;
  final Future<void> Function() onLoadMore;
  final VoidCallback onReload;
  final Widget Function(BuildContext context, T item) itemBuilder;
  final String Function(AppLocalizations l10n, ApiException error) errorMessage;
  final String emptyTitle;
  final String? emptyMessage;
  final IconData emptyIcon;
  final Widget? emptyAction;
  final Widget? header;
  final bool showCount;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    switch (state.phase) {
      case PagedPhase.loading:
        return const LoadingView();
      case PagedPhase.error:
        return ErrorView(
          message: errorMessage(l10n, state.error!),
          onRetry: () async => onReload(),
        );
      case PagedPhase.ready:
        break;
    }
    final items = state.items;
    if (items.isEmpty) {
      return Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          EmptyView(icon: emptyIcon, title: emptyTitle, message: emptyMessage),
          ?emptyAction,
        ],
      );
    }
    final headerCount = (header != null ? 1 : 0) + (showCount ? 1 : 0);
    return RefreshIndicator(
      onRefresh: () async => onReload(),
      child: ListView.builder(
        itemCount: items.length + headerCount + 1,
        itemBuilder: (context, index) {
          var cursor = index;
          if (header != null) {
            if (cursor == 0) return header!;
            cursor--;
          }
          if (showCount) {
            if (cursor == 0) {
              return Padding(
                padding: const EdgeInsets.only(bottom: RacheetaSpacing.sm),
                child: Text(
                  l10n.resultsCount(state.count),
                  key: const Key('paged-count'),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              );
            }
            cursor--;
          }
          if (cursor == items.length) {
            return _Footer(state: state, onLoadMore: onLoadMore);
          }
          return itemBuilder(context, items[cursor]);
        },
      ),
    );
  }
}

class _Footer<T> extends StatelessWidget {
  const _Footer({required this.state, required this.onLoadMore});
  final PagedState<T> state;
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
            Text(
              l10n.loadMoreFailed,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
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
