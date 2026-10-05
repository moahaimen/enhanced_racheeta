import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/page.dart';
import '../../../core/paging/paged_notifier.dart';
import '../../../shared/search/search_query.dart';
import '../../auth/application/account_scope.dart';
import '../../auth/application/providers.dart';
import '../../auth/application/session_state.dart';
import '../data/real_estate_api.dart';
import '../data/real_estate_models.dart';
import '../provider_capability.dart';

final Provider<RealEstateApi> realEstateApiProvider = Provider<RealEstateApi>(
  (ref) => RealEstateApi(ref.watch(apiClientProvider)),
);

/// Whether the signed-in account may use the property-owner workspace, from the live `/me` data.
final Provider<bool> canUseSellerWorkspaceProvider = Provider<bool>((ref) {
  final session = ref.watch(sessionControllerProvider);
  return session is SessionAuthenticated &&
      session.account.hasPermission(realEstateSellerCapability);
});

/// The search form of the public catalogue; reset when the account changes.
class ListingQueryController extends Notifier<SearchQuery> {
  @override
  SearchQuery build() {
    ref.watch(accountIdProvider);
    return const SearchQuery();
  }

  void update(SearchQuery next) => state = next;
}

final listingQueryProvider =
    NotifierProvider<ListingQueryController, SearchQuery>(
      ListingQueryController.new,
      retry: noRetry,
    );

/// Public catalogue results. Rebuilt (epoch bumped, requests cancelled, late responses dropped)
/// whenever the query or the account changes, so an older query's answer can never replace the
/// current one and page N of one query is never appended to another.
class ListingsController extends PagedNotifier<PropertyListing> {
  late SearchQuery _query;

  @override
  PagedState<PropertyListing> build() {
    ref.watch(accountIdProvider);
    _query = ref.watch(listingQueryProvider);
    return start();
  }

  @override
  Future<Page<PropertyListing>> fetchPage(int page, CancelToken token) => ref
      .read(realEstateApiProvider)
      .listings(
        _query,
        page: page,
        pageSize: PagedNotifier.pageSize,
        cancelToken: token,
      );
}

final listingsProvider =
    NotifierProvider<ListingsController, PagedState<PropertyListing>>(
      ListingsController.new,
      retry: noRetry,
    );

/// One public listing (public data, kept per id and disposed with the screen).
final listingDetailProvider = FutureProvider.autoDispose
    .family<PropertyListing, String>((ref, id) {
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      return ref.watch(realEstateApiProvider).listing(id, cancelToken: token);
    }, retry: noRetry);

/// The owner's dashboard, keyed by account so another account never sees this one's counts.
final ownerDashboardProvider = FutureProvider.autoDispose
    .family<OwnerDashboard, String?>((ref, accountId) {
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      return ref
          .watch(realEstateApiProvider)
          .ownerDashboard(cancelToken: token);
    }, retry: noRetry);

/// The caller's own listings. Rebuilt on an account change; invalidated after a lifecycle change.
class OwnerListingsController extends PagedNotifier<PropertyListing> {
  @override
  PagedState<PropertyListing> build() {
    ref.watch(accountIdProvider);
    return start();
  }

  @override
  Future<Page<PropertyListing>> fetchPage(int page, CancelToken token) => ref
      .read(realEstateApiProvider)
      .ownerListings(
        page: page,
        pageSize: PagedNotifier.pageSize,
        cancelToken: token,
      );
}

final ownerListingsProvider =
    NotifierProvider<OwnerListingsController, PagedState<PropertyListing>>(
      OwnerListingsController.new,
      retry: noRetry,
    );

final ownerListingDetailProvider = FutureProvider.autoDispose
    .family<PropertyListing, AccountScoped<String>>((ref, key) {
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      return ref
          .watch(realEstateApiProvider)
          .ownerListing(key.value, cancelToken: token);
    }, retry: noRetry);
