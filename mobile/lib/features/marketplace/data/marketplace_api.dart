import 'package:dio/dio.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/page.dart';
import '../../../shared/search/search_query.dart';
import 'marketplace_models.dart';

/// The one filter the provider catalogue documents.
abstract final class ProductFilterKeys {
  static const category = 'category';
}

/// Provider-facing catalogue and the medical company's own products. The backend decides targeting
/// (who sees what), ownership and the publication gate.
class MarketplaceApi {
  const MarketplaceApi(this._client);
  final ApiClient _client;

  /// `GET /marketplace/categories` (active, unpaginated reference data).
  Future<List<ProductCategory>> categories({CancelToken? cancelToken}) =>
      _client.get<List<ProductCategory>>(
        '/api/v1/marketplace/categories',
        parse: (json) {
          if (json is! List) throw const FormatException('Expected a list.');
          return List<ProductCategory>.unmodifiable(
            json.map(ProductCategory.fromJson),
          );
        },
        auth: false,
        cancelToken: cancelToken,
      );

  /// `GET /marketplace/products` (verified providers only; targeted, paginated, newest first).
  Future<Page<Product>> products(
    SearchQuery query, {
    int page = 1,
    int pageSize = 20,
    CancelToken? cancelToken,
  }) => _client.getPage<Product>(
    '/api/v1/marketplace/products',
    parseItem: Product.fromPublicJson,
    page: page,
    pageSize: pageSize,
    // the catalogue documents no free-text search: only the filters in the query are sent
    query: {...query.filters},
    cancelToken: cancelToken,
  );

  /// `GET /marketplace/products/{id}` (404 outside the provider's audience).
  Future<Product> product(String id, {CancelToken? cancelToken}) =>
      _client.get<Product>(
        '/api/v1/marketplace/products/${Uri.encodeComponent(id)}',
        parse: Product.fromPublicJson,
        cancelToken: cancelToken,
      );

  /// `GET /marketplace/company/dashboard`.
  Future<CompanyDashboard> companyDashboard({CancelToken? cancelToken}) =>
      _client.get<CompanyDashboard>(
        '/api/v1/marketplace/company/dashboard',
        parse: CompanyDashboard.fromJson,
        cancelToken: cancelToken,
      );

  /// `GET /marketplace/company/products` (own products, paginated, newest first).
  Future<Page<Product>> companyProducts({
    int page = 1,
    int pageSize = 20,
    CancelToken? cancelToken,
  }) => _client.getPage<Product>(
    '/api/v1/marketplace/company/products',
    parseItem: Product.fromOwnerJson,
    page: page,
    pageSize: pageSize,
    cancelToken: cancelToken,
  );

  /// `GET /marketplace/company/products/{id}` (a foreign id is a plain 404).
  Future<Product> companyProduct(String id, {CancelToken? cancelToken}) =>
      _client.get<Product>(
        '/api/v1/marketplace/company/products/${Uri.encodeComponent(id)}',
        parse: Product.fromOwnerJson,
        cancelToken: cancelToken,
      );

  /// `POST /marketplace/company/products/{id}/activate`: the publication gate decides. No body,
  /// never retried.
  Future<Product> activate(
    String id, {
    CancelToken? cancelToken,
  }) => _client.post<Product>(
    '/api/v1/marketplace/company/products/${Uri.encodeComponent(id)}/activate',
    parse: Product.fromOwnerJson,
    cancelToken: cancelToken,
  );

  /// `POST /marketplace/company/products/{id}/deactivate`. No body, never retried.
  Future<Product> deactivate(
    String id, {
    CancelToken? cancelToken,
  }) => _client.post<Product>(
    '/api/v1/marketplace/company/products/${Uri.encodeComponent(id)}/deactivate',
    parse: Product.fromOwnerJson,
    cancelToken: cancelToken,
  );
}
