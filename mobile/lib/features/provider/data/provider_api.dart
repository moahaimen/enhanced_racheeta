import 'package:dio/dio.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/page.dart';
import '../../../core/time/instants.dart';
import '../../reservations/data/reservation_models.dart';
import 'provider_models.dart';

/// Provider-side endpoints (dashboards, appointment availability, received reservations, own
/// services). All require a PROVIDER account with a provider profile; the backend scopes every
/// query to the caller's own profile and answers 404 for anything else.
class ProviderApi {
  const ProviderApi(this._client);
  final ApiClient _client;

  /// `GET /dashboards/`: which dashboards this account may open right now.
  Future<DashboardIndex> dashboardIndex({CancelToken? cancelToken}) =>
      _client.get<DashboardIndex>(
        '/api/v1/dashboards/',
        parse: DashboardIndex.fromJson,
        cancelToken: cancelToken,
      );

  /// `GET /dashboards/doctor` or `/dashboards/facility` (parameterless, read-only).
  Future<ProviderDashboard> dashboard(
    ProviderDashboardKind kind, {
    CancelToken? cancelToken,
  }) => _client.get<ProviderDashboard>(
    '/api/v1/dashboards/${kind.wire}',
    parse: (json) => ProviderDashboard.fromJson(kind, json),
    cancelToken: cancelToken,
  );

  /// `GET /providers/me/services` (unpaginated).
  Future<List<OwnService>> services({CancelToken? cancelToken}) =>
      _client.get<List<OwnService>>(
        '/api/v1/providers/me/services',
        parse: (json) {
          if (json is! List) throw const FormatException('Expected a list.');
          return List<OwnService>.unmodifiable(json.map(OwnService.fromJson));
        },
        cancelToken: cancelToken,
      );

  /// `GET /reservations/provider/availability` (paginated, soonest first, includes inactive and
  /// past slots).
  Future<Page<ProviderSlot>> slots({
    int page = 1,
    int pageSize = 100,
    CancelToken? cancelToken,
  }) => _client.getPage<ProviderSlot>(
    '/api/v1/reservations/provider/availability',
    parseItem: ProviderSlot.fromJson,
    page: page,
    pageSize: pageSize,
    cancelToken: cancelToken,
  );

  /// `POST /reservations/provider/availability {service, starts_at}` → 201. The end time is the
  /// backend's (start + the service duration); overlap and "must be in the future" are its rules.
  /// Never retried automatically.
  Future<ProviderSlot> createSlot({
    required String serviceId,
    required DateTime startsAt,
    CancelToken? cancelToken,
  }) => _client.post<ProviderSlot>(
    '/api/v1/reservations/provider/availability',
    body: <String, Object?>{
      'service': serviceId,
      'starts_at': toWireInstant(startsAt),
    },
    parse: ProviderSlot.fromJson,
    cancelToken: cancelToken,
  );

  /// `DELETE /reservations/provider/availability/{id}` → 204 (deactivates an unbooked slot).
  Future<void> deactivateSlot(String id, {CancelToken? cancelToken}) =>
      _client.deleteNoContent(
        '/api/v1/reservations/provider/availability/${Uri.encodeComponent(id)}',
        cancelToken: cancelToken,
      );

  /// `GET /reservations/provider` (paginated, newest appointment first).
  Future<Page<ProviderReservation>> reservations({
    int page = 1,
    int pageSize = 20,
    CancelToken? cancelToken,
  }) => _client.getPage<ProviderReservation>(
    '/api/v1/reservations/provider',
    parseItem: ProviderReservation.fromJson,
    page: page,
    pageSize: pageSize,
    cancelToken: cancelToken,
  );

  /// `GET /reservations/provider/{id}`.
  Future<ProviderReservation> reservation(
    String id, {
    CancelToken? cancelToken,
  }) => _client.get<ProviderReservation>(
    '/api/v1/reservations/provider/${Uri.encodeComponent(id)}',
    parse: ProviderReservation.fromJson,
    cancelToken: cancelToken,
  );

  /// `POST /reservations/provider/{id}/transition {status}` → the updated reservation. The backend
  /// decides whether the transition is allowed; never retried automatically.
  Future<ProviderReservation> transition(
    String id,
    ReservationStatus target, {
    CancelToken? cancelToken,
  }) => _client.post<ProviderReservation>(
    '/api/v1/reservations/provider/${Uri.encodeComponent(id)}/transition',
    body: <String, Object?>{'status': target.wire},
    parse: ProviderReservation.fromJson,
    cancelToken: cancelToken,
  );
}
