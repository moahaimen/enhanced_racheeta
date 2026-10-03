import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_exception.dart';
import '../api/page.dart';

/// Providers here must not auto-retry: a failed load is reported once and the user decides.
Duration? noRetry(int retryCount, Object error) => null;

enum PagedPhase { loading, ready, error }

/// Immutable state of a paginated list.
@immutable
class PagedState<T> {
  const PagedState({
    this.phase = PagedPhase.loading,
    this.items = const [],
    this.count = 0,
    this.nextPage,
    this.loadingMore = false,
    this.error,
    this.loadMoreError,
  });

  final PagedPhase phase;
  final List<T> items;
  final int count;

  /// The page number to request next; null when the last page was loaded.
  final int? nextPage;
  final bool loadingMore;

  /// First-page failure (the list is replaced by an error view with retry).
  final ApiException? error;

  /// A failure while loading a later page (items already shown are kept).
  final ApiException? loadMoreError;

  bool get hasMore => nextPage != null;
}

/// Base for paginated lists backed by the shared API client.
///
/// Stale-result protection: every (re)build starts a new *epoch* and cancels the previous
/// requests; a response is applied only when its epoch is still current and the notifier is still
/// mounted. Subclasses `ref.watch` whatever the list depends on (filters, the signed-in account),
/// so changing a filter or switching accounts rebuilds the notifier, bumps the epoch and discards
/// every late response of the previous query.
abstract class PagedNotifier<T> extends Notifier<PagedState<T>> {
  static const int pageSize = 20;

  int _epoch = 0;
  CancelToken? _token;

  /// Fetches one page (1-based). Must use [token] for the HTTP request.
  Future<Page<T>> fetchPage(int page, CancelToken token);

  /// Subclasses call this at the end of `build()` after watching their dependencies.
  PagedState<T> start() {
    _epoch++;
    _token?.cancel('superseded');
    final token = _token = CancelToken();
    ref.onDispose(() => token.cancel('disposed'));
    final epoch = _epoch;
    unawaited(Future<void>.microtask(() => _load(1, epoch, token)));
    return PagedState<T>();
  }

  /// Retries the first page (also pull-to-refresh).
  void reload() => ref.invalidateSelf();

  Future<void> loadMore() async {
    final next = state.nextPage;
    if (next == null || state.loadingMore || state.phase != PagedPhase.ready) {
      return;
    }
    final token = _token;
    if (token == null) return;
    state = PagedState<T>(
      phase: PagedPhase.ready,
      items: state.items,
      count: state.count,
      nextPage: next,
      loadingMore: true,
    );
    await _load(next, _epoch, token);
  }

  Future<void> _load(int page, int epoch, CancelToken token) async {
    try {
      final result = await fetchPage(page, token);
      if (!_isCurrent(epoch)) return;
      state = PagedState<T>(
        phase: PagedPhase.ready,
        items: page == 1 ? result.results : [...state.items, ...result.results],
        count: result.count,
        nextPage: result.hasNext ? page + 1 : null,
      );
    } on StaleSessionException {
      // The session ended; the account change rebuilds this notifier.
    } on ApiException catch (error) {
      if (!_isCurrent(epoch) || error.kind == ApiErrorKind.cancelled) return;
      state = page == 1
          ? PagedState<T>(phase: PagedPhase.error, error: error)
          : PagedState<T>(
              phase: PagedPhase.ready,
              items: state.items,
              count: state.count,
              nextPage: page,
              loadMoreError: error,
            );
    }
  }

  bool _isCurrent(int epoch) => ref.mounted && epoch == _epoch;
}
