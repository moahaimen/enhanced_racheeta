import 'package:dio/dio.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/page.dart';
import '../../../core/time/instants.dart';
import 'discovery_models.dart';

/// Search and filter state accepted by `GET /providers` (`providers_list` in the OpenAPI file).
/// Only the documented query parameters exist here.
class DiscoveryFilters {
  const DiscoveryFilters({
    this.search = '',
    this.kind,
    this.type,
    this.specialtySlug,
    this.governorateId,
    this.cityId,
    this.ordering = DiscoveryOrdering.nameAsc,
  });

  final String search;

  /// `PRACTITIONER` | `FACILITY`.
  final String? kind;

  /// `ProviderTypeEnum` code.
  final String? type;
  final String? specialtySlug;
  final String? governorateId;
  final String? cityId;
  final DiscoveryOrdering ordering;

  bool get isDefault => this == const DiscoveryFilters();

  /// Number of narrowing filters in use (ordering and search text excluded).
  int get activeFilterCount => [
    kind,
    type,
    specialtySlug,
    governorateId,
    cityId,
  ].where((value) => value != null).length;

  /// Changing the governorate invalidates the city (cities belong to one governorate).
  DiscoveryFilters copyWith({
    String? search,
    Object? kind = _keep,
    Object? type = _keep,
    Object? specialtySlug = _keep,
    Object? governorateId = _keep,
    Object? cityId = _keep,
    DiscoveryOrdering? ordering,
  }) {
    final nextGovernorate = identical(governorateId, _keep)
        ? this.governorateId
        : governorateId as String?;
    final governorateChanged = nextGovernorate != this.governorateId;
    return DiscoveryFilters(
      search: search ?? this.search,
      kind: identical(kind, _keep) ? this.kind : kind as String?,
      type: identical(type, _keep) ? this.type : type as String?,
      specialtySlug: identical(specialtySlug, _keep)
          ? this.specialtySlug
          : specialtySlug as String?,
      governorateId: nextGovernorate,
      cityId: governorateChanged
          ? (identical(cityId, _keep) ? null : cityId as String?)
          : (identical(cityId, _keep) ? this.cityId : cityId as String?),
      ordering: ordering ?? this.ordering,
    );
  }

  Map<String, Object?> toQuery() => <String, Object?>{
    if (search.trim().isNotEmpty) 'search': search.trim(),
    'kind': ?kind,
    'type': ?type,
    'specialty': ?specialtySlug,
    'governorate': ?governorateId,
    'city': ?cityId,
    if (ordering != DiscoveryOrdering.nameAsc) 'ordering': ordering.wire,
  };

  @override
  bool operator ==(Object other) =>
      other is DiscoveryFilters &&
      other.search == search &&
      other.kind == kind &&
      other.type == type &&
      other.specialtySlug == specialtySlug &&
      other.governorateId == governorateId &&
      other.cityId == cityId &&
      other.ordering == ordering;

  @override
  int get hashCode => Object.hash(
    search,
    kind,
    type,
    specialtySlug,
    governorateId,
    cityId,
    ordering,
  );
}

const Object _keep = Object();

/// `ordering` values documented for `GET /providers`.
enum DiscoveryOrdering {
  nameAsc('display_name'),
  nameDesc('-display_name'),
  newest('-created_at'),
  oldest('created_at');

  const DiscoveryOrdering(this.wire);
  final String wire;
}

/// How far ahead public availability is requested. The endpoint is not paginated, so the window
/// bounds the response; the user can still only book what the backend lists.
const Duration availabilityWindow = Duration(days: 30);

/// Provider discovery, profile, availability and the reference data behind the filters. Thin and
/// typed; business rules (eligibility, visibility, availability) stay on the backend.
class DiscoveryApi {
  const DiscoveryApi(this._client);
  final ApiClient _client;

  /// `GET /providers` (verified and visible providers only; paginated).
  Future<Page<ProviderCard>> searchProviders(
    DiscoveryFilters filters, {
    int page = 1,
    int pageSize = 20,
    CancelToken? cancelToken,
  }) => _client.getPage<ProviderCard>(
    '/api/v1/providers',
    parseItem: ProviderCard.fromJson,
    page: page,
    pageSize: pageSize,
    query: filters.toQuery(),
    cancelToken: cancelToken,
  );

  /// `GET /providers/{id}`.
  Future<ProviderPublic> provider(String id, {CancelToken? cancelToken}) =>
      _client.get<ProviderPublic>(
        '/api/v1/providers/${Uri.encodeComponent(id)}',
        parse: ProviderPublic.fromJson,
        cancelToken: cancelToken,
      );

  /// `GET /providers/{id}/availability?service&from&to` (unpaginated, soonest first).
  /// `from`/`to` are UTC instants.
  Future<List<AvailabilitySlot>> availability(
    String providerId, {
    required String serviceId,
    required DateTime from,
    required DateTime to,
    CancelToken? cancelToken,
  }) => _client.get<List<AvailabilitySlot>>(
    '/api/v1/providers/${Uri.encodeComponent(providerId)}/availability',
    query: <String, Object?>{
      'service': serviceId,
      'from': toWireInstant(from),
      'to': toWireInstant(to),
    },
    parse: (json) {
      if (json is! List) throw const FormatException('Expected a list.');
      return List<AvailabilitySlot>.unmodifiable(
        json.map(AvailabilitySlot.fromJson),
      );
    },
    cancelToken: cancelToken,
  );

  /// `GET /specialties` (active, unpaginated).
  Future<List<Specialty>> specialties({CancelToken? cancelToken}) =>
      _client.get<List<Specialty>>(
        '/api/v1/specialties',
        parse: (json) => _list(json, Specialty.fromJson),
        cancelToken: cancelToken,
      );

  /// `GET /geo/governorates`.
  Future<List<Place>> governorates({CancelToken? cancelToken}) =>
      _client.get<List<Place>>(
        '/api/v1/geo/governorates',
        parse: (json) => _list(json, Place.fromJson),
        cancelToken: cancelToken,
      );

  /// `GET /geo/cities?governorate=`.
  Future<List<Place>> cities(
    String governorateId, {
    CancelToken? cancelToken,
  }) => _client.get<List<Place>>(
    '/api/v1/geo/cities',
    query: <String, Object?>{'governorate': governorateId},
    parse: (json) => _list(json, Place.fromJson),
    cancelToken: cancelToken,
  );

  static List<T> _list<T>(Object? json, T Function(Object?) parse) {
    if (json is! List) throw const FormatException('Expected a list.');
    return List<T>.unmodifiable(json.map(parse));
  }
}
