import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/page.dart';
import '../../../core/paging/paged_notifier.dart';
import '../../../core/time/time_providers.dart';
import '../../auth/application/account_scope.dart';
import '../../auth/application/providers.dart';
import '../data/discovery_api.dart';
import '../data/discovery_models.dart';

final Provider<DiscoveryApi> discoveryApiProvider = Provider<DiscoveryApi>(
  (ref) => DiscoveryApi(ref.watch(apiClientProvider)),
);

/// The search form: text, filters and ordering. Reset when the account changes.
class DiscoveryFiltersController extends Notifier<DiscoveryFilters> {
  @override
  DiscoveryFilters build() {
    ref.watch(accountIdProvider);
    return const DiscoveryFilters();
  }

  void update(DiscoveryFilters next) => state = next;
}

final discoveryFiltersProvider =
    NotifierProvider<DiscoveryFiltersController, DiscoveryFilters>(
      DiscoveryFiltersController.new,
      retry: noRetry,
    );

/// Paginated search results. Rebuilt (epoch bumped, in-flight requests cancelled, late responses
/// dropped) whenever the filters or the account change, so results of an older query can never
/// replace the current ones, and page N of one query is never appended to another.
class ProviderSearchController extends PagedNotifier<ProviderCard> {
  late DiscoveryFilters _filters;

  @override
  PagedState<ProviderCard> build() {
    ref.watch(accountIdProvider);
    _filters = ref.watch(discoveryFiltersProvider);
    return start();
  }

  @override
  Future<Page<ProviderCard>> fetchPage(int page, CancelToken token) => ref
      .read(discoveryApiProvider)
      .searchProviders(
        _filters,
        page: page,
        pageSize: PagedNotifier.pageSize,
        cancelToken: token,
      );
}

final providerSearchProvider =
    NotifierProvider<ProviderSearchController, PagedState<ProviderCard>>(
      ProviderSearchController.new,
      retry: noRetry,
    );

/// Reference data for the filters. Public and rarely changing: kept for the app's lifetime but
/// reloaded after an account change.
final specialtiesProvider = FutureProvider<List<Specialty>>((ref) {
  ref.watch(accountIdProvider);
  return ref.watch(discoveryApiProvider).specialties();
}, retry: noRetry);

final governoratesProvider = FutureProvider<List<Place>>((ref) {
  ref.watch(accountIdProvider);
  return ref.watch(discoveryApiProvider).governorates();
}, retry: noRetry);

final citiesProvider = FutureProvider.family<List<Place>, String>((
  ref,
  governorateId,
) {
  ref.watch(accountIdProvider);
  return ref.watch(discoveryApiProvider).cities(governorateId);
}, retry: noRetry);

/// `GET /providers/{id}`; autodisposed with the screen (cancelling the request).
final providerDetailProvider = FutureProvider.autoDispose
    .family<ProviderPublic, String>((ref, id) {
      ref.watch(accountIdProvider);
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      return ref.watch(discoveryApiProvider).provider(id, cancelToken: token);
    }, retry: noRetry);

typedef AvailabilityQuery = ({String providerId, String serviceId});

/// Live availability for one provider service within [availabilityWindow]. The list is exactly what
/// the backend returned; it is a snapshot, not a promise (booking re-validates).
final availabilityProvider = FutureProvider.autoDispose
    .family<List<AvailabilitySlot>, AvailabilityQuery>((ref, query) {
      ref.watch(accountIdProvider);
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      final now = ref.read(nowProvider)();
      return ref
          .watch(discoveryApiProvider)
          .availability(
            query.providerId,
            serviceId: query.serviceId,
            from: now,
            to: now.add(availabilityWindow),
            cancelToken: token,
          );
    }, retry: noRetry);
