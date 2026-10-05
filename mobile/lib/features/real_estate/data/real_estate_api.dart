import 'package:dio/dio.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/page.dart';
import '../../../shared/search/search_query.dart';
import 'real_estate_models.dart';

/// Backend filter parameters of `GET /real-estate/listings` the app sends (all documented).
abstract final class ListingFilterKeys {
  static const transaction = 'transaction_type';
  static const propertyType = 'property_type';
  static const governorate = 'governorate';
  static const ordering = 'ordering';
}

/// Public catalogue and the seller's own workspace. The backend decides visibility, ownership and
/// publication; the app never filters or reorders results.
class RealEstateApi {
  const RealEstateApi(this._client);
  final ApiClient _client;

  /// `GET /real-estate/listings` (public, paginated).
  Future<Page<PropertyListing>> listings(
    SearchQuery query, {
    int page = 1,
    int pageSize = 20,
    CancelToken? cancelToken,
  }) => _client.getPage<PropertyListing>(
    '/api/v1/real-estate/listings',
    parseItem: PropertyListing.fromPublicJson,
    page: page,
    pageSize: pageSize,
    query: query.toQuery(),
    auth: false,
    cancelToken: cancelToken,
  );

  /// `GET /real-estate/listings/{id}` (404 unless publicly visible).
  Future<PropertyListing> listing(String id, {CancelToken? cancelToken}) =>
      _client.get<PropertyListing>(
        '/api/v1/real-estate/listings/${Uri.encodeComponent(id)}',
        parse: PropertyListing.fromPublicJson,
        auth: false,
        cancelToken: cancelToken,
      );

  /// `GET /real-estate/owner/dashboard`.
  Future<OwnerDashboard> ownerDashboard({CancelToken? cancelToken}) =>
      _client.get<OwnerDashboard>(
        '/api/v1/real-estate/owner/dashboard',
        parse: OwnerDashboard.fromJson,
        cancelToken: cancelToken,
      );

  /// `GET /real-estate/owner/listings` (own listings, paginated, newest first).
  Future<Page<PropertyListing>> ownerListings({
    int page = 1,
    int pageSize = 20,
    CancelToken? cancelToken,
  }) => _client.getPage<PropertyListing>(
    '/api/v1/real-estate/owner/listings',
    parseItem: PropertyListing.fromOwnerJson,
    page: page,
    pageSize: pageSize,
    cancelToken: cancelToken,
  );

  /// `GET /real-estate/owner/listings/{id}` (a foreign id is a plain 404).
  Future<PropertyListing> ownerListing(String id, {CancelToken? cancelToken}) =>
      _client.get<PropertyListing>(
        '/api/v1/real-estate/owner/listings/${Uri.encodeComponent(id)}',
        parse: PropertyListing.fromOwnerJson,
        cancelToken: cancelToken,
      );

  /// `POST /real-estate/owner/listings/{id}/publish`: the backend's publication gate decides.
  /// No body, never retried.
  Future<PropertyListing> publish(String id, {CancelToken? cancelToken}) =>
      _client.post<PropertyListing>(
        '/api/v1/real-estate/owner/listings/${Uri.encodeComponent(id)}/publish',
        parse: PropertyListing.fromOwnerJson,
        cancelToken: cancelToken,
      );

  /// `POST /real-estate/owner/listings/{id}/unpublish`. No body, never retried.
  Future<PropertyListing> unpublish(
    String id, {
    CancelToken? cancelToken,
  }) => _client.post<PropertyListing>(
    '/api/v1/real-estate/owner/listings/${Uri.encodeComponent(id)}/unpublish',
    parse: PropertyListing.fromOwnerJson,
    cancelToken: cancelToken,
  );
}
