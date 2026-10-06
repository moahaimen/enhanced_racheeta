import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/page.dart';
import '../../../core/paging/paged_notifier.dart';
import '../../../shared/search/search_query.dart';
import '../../auth/application/account_scope.dart';
import '../../auth/application/providers.dart';
import '../../auth/application/session_state.dart';
import '../data/marketplace_api.dart';
import '../data/marketplace_models.dart';
import '../provider_capability.dart';

final Provider<MarketplaceApi> marketplaceApiProvider =
    Provider<MarketplaceApi>(
      (ref) => MarketplaceApi(ref.watch(apiClientProvider)),
    );

/// Whether the signed-in account's `/me` lists the marketplace-browsing capability (live).
final Provider<bool> canBrowseMarketplaceProvider = Provider<bool>((ref) {
  final session = ref.watch(sessionControllerProvider);
  return session is SessionAuthenticated &&
      session.account.hasPermission(marketplaceBrowseCapability);
});

/// Whether the signed-in account's `/me` lists the company-workspace capability (live).
final Provider<bool> canUseCompanyWorkspaceProvider = Provider<bool>((ref) {
  final session = ref.watch(sessionControllerProvider);
  return session is SessionAuthenticated &&
      session.account.hasPermission(marketplaceCompanyCapability);
});

/// Category options for the filter (public reference data).
final categoriesProvider = FutureProvider<List<ProductCategory>>((ref) {
  final token = CancelToken();
  ref.onDispose(() => token.cancel('disposed'));
  return ref.watch(marketplaceApiProvider).categories(cancelToken: token);
}, retry: noRetry);

/// The catalogue filter; reset when the account changes.
class ProductQueryController extends Notifier<SearchQuery> {
  @override
  SearchQuery build() {
    ref.watch(accountIdProvider);
    return const SearchQuery();
  }

  void update(SearchQuery next) => state = next;
}

final productQueryProvider =
    NotifierProvider<ProductQueryController, SearchQuery>(
      ProductQueryController.new,
      retry: noRetry,
    );

/// The provider's targeted catalogue. Targeting is per provider, so the list is rebuilt (epoch
/// bumped, requests cancelled, late answers dropped) whenever the filter or the account changes.
class ProductsController extends PagedNotifier<Product> {
  late SearchQuery _query;

  @override
  PagedState<Product> build() {
    ref.watch(accountIdProvider);
    _query = ref.watch(productQueryProvider);
    return start();
  }

  @override
  Future<Page<Product>> fetchPage(int page, CancelToken token) => ref
      .read(marketplaceApiProvider)
      .products(
        _query,
        page: page,
        pageSize: PagedNotifier.pageSize,
        cancelToken: token,
      );
}

final productsProvider =
    NotifierProvider<ProductsController, PagedState<Product>>(
      ProductsController.new,
      retry: noRetry,
    );

/// One catalogue product, keyed by account (what a provider may see depends on that provider).
final productDetailProvider = FutureProvider.autoDispose
    .family<Product, AccountScoped<String>>((ref, key) {
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      return ref
          .watch(marketplaceApiProvider)
          .product(key.value, cancelToken: token);
    }, retry: noRetry);

final companyDashboardProvider = FutureProvider.autoDispose
    .family<CompanyDashboard, String?>((ref, accountId) {
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      return ref
          .watch(marketplaceApiProvider)
          .companyDashboard(cancelToken: token);
    }, retry: noRetry);

class CompanyProductsController extends PagedNotifier<Product> {
  @override
  PagedState<Product> build() {
    ref.watch(accountIdProvider);
    return start();
  }

  @override
  Future<Page<Product>> fetchPage(int page, CancelToken token) => ref
      .read(marketplaceApiProvider)
      .companyProducts(
        page: page,
        pageSize: PagedNotifier.pageSize,
        cancelToken: token,
      );
}

final companyProductsProvider =
    NotifierProvider<CompanyProductsController, PagedState<Product>>(
      CompanyProductsController.new,
      retry: noRetry,
    );

final companyProductDetailProvider = FutureProvider.autoDispose
    .family<Product, AccountScoped<String>>((ref, key) {
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      return ref
          .watch(marketplaceApiProvider)
          .companyProduct(key.value, cancelToken: token);
    }, retry: noRetry);
