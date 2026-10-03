import 'package:dio/dio.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/page.dart';
import 'reservation_models.dart';

/// Patient reservation endpoints (`/reservations`, `/reservations/me*`). All require a PATIENT
/// account; the backend scopes every query to the caller and answers 404 for anything else.
class ReservationsApi {
  const ReservationsApi(this._client);
  final ApiClient _client;

  /// `POST /reservations {availability_slot, patient_note}` → 201.
  ///
  /// Never retried automatically: the endpoint has no idempotency key, so a repeat after an
  /// ambiguous failure could double-book. (The client's single post-refresh replay only happens
  /// after a 401, i.e. when the request was rejected before it was processed.)
  Future<Reservation> create({
    required String slotId,
    String note = '',
    CancelToken? cancelToken,
  }) => _client.post<Reservation>(
    '/api/v1/reservations',
    body: <String, Object?>{
      'availability_slot': slotId,
      if (note.trim().isNotEmpty) 'patient_note': note.trim(),
    },
    parse: Reservation.fromJson,
    cancelToken: cancelToken,
  );

  /// `GET /reservations/me` (paginated, newest appointment first).
  Future<Page<Reservation>> list({
    int page = 1,
    int pageSize = 20,
    CancelToken? cancelToken,
  }) => _client.getPage<Reservation>(
    '/api/v1/reservations/me',
    parseItem: Reservation.fromJson,
    page: page,
    pageSize: pageSize,
    cancelToken: cancelToken,
  );

  /// `GET /reservations/me/{id}`.
  Future<Reservation> detail(String id, {CancelToken? cancelToken}) =>
      _client.get<Reservation>(
        '/api/v1/reservations/me/${Uri.encodeComponent(id)}',
        parse: Reservation.fromJson,
        cancelToken: cancelToken,
      );

  /// `POST /reservations/me/{id}/cancel {reason}` → the updated reservation. The backend decides
  /// eligibility (status and start time) and answers `invalid_transition` otherwise.
  Future<Reservation> cancel(String id, {CancelToken? cancelToken}) =>
      _client.post<Reservation>(
        '/api/v1/reservations/me/${Uri.encodeComponent(id)}/cancel',
        body: const <String, Object?>{},
        parse: Reservation.fromJson,
        cancelToken: cancelToken,
      );
}
