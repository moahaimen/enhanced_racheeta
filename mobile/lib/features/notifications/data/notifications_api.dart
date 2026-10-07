import 'package:dio/dio.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/page.dart';
import 'notification_models.dart';

/// Persistent notifications and push-device registration. Every call is the caller's own: the
/// backend scopes lists and marks to the authenticated account.
class NotificationsApi {
  const NotificationsApi(this._client);
  final ApiClient _client;

  /// `GET /notifications/` (newest first, paginated).
  Future<Page<AppNotification>> notifications({
    int page = 1,
    int pageSize = 20,
    CancelToken? cancelToken,
  }) => _client.getPage<AppNotification>(
    '/api/v1/notifications/',
    parseItem: AppNotification.fromJson,
    page: page,
    pageSize: pageSize,
    cancelToken: cancelToken,
  );

  /// `GET /notifications/unread-count/` (the authoritative count).
  Future<int> unreadCount({CancelToken? cancelToken}) => _client.get<int>(
    '/api/v1/notifications/unread-count/',
    parse: parseCount,
    cancelToken: cancelToken,
  );

  /// `POST /notifications/{id}/read/` (empty JSON object) → the updated notification. Never retried.
  Future<AppNotification> markRead(String id, {CancelToken? cancelToken}) =>
      _client.post<AppNotification>(
        '/api/v1/notifications/${Uri.encodeComponent(id)}/read/',
        body: const <String, Object?>{},
        parse: AppNotification.fromJson,
        cancelToken: cancelToken,
      );

  /// `POST /notifications/read-all/` (empty JSON object) → how many rows changed. Never retried.
  Future<int> markAllRead({CancelToken? cancelToken}) => _client.post<int>(
    '/api/v1/notifications/read-all/',
    body: const <String, Object?>{},
    parse: parseUpdated,
    cancelToken: cancelToken,
  );

  /// `POST /notifications/push-devices/` — idempotent, ORDERED upsert of this device's FCM token
  /// for the account that owns [bearer] (a token owned by another account is transferred to it).
  /// [ownershipSeq] is the strictly increasing installation sequence: the server applies the
  /// request only if it is newer than the one stored for the token, so the final owner does not
  /// depend on request arrival order (a superseded request is answered `409 stale_ownership`).
  /// Sent *detached* from the session (see `ApiClient.postDetached`) by the push-ownership lane.
  Future<void> registerDevice(
    String token, {
    required String bearer,
    required int ownershipSeq,
    String platform = 'ANDROID',
  }) => _client.postDetached<void>(
    '/api/v1/notifications/push-devices/',
    bearer: bearer,
    body: {'token': token, 'platform': platform, 'ownership_seq': ownershipSeq},
    parse: (_) {},
  );

  /// `POST /notifications/push-devices/unregister/` (204): ordered like [registerDevice]; a newer
  /// sequence deactivates the owner's registration and stores the sequence, so an older register
  /// that arrives later cannot resurrect it. Detached so it can complete after the session ended.
  Future<void> unregisterDevice(
    String token, {
    required String bearer,
    required int ownershipSeq,
    String platform = 'ANDROID',
  }) => _client.postNoContentDetached(
    '/api/v1/notifications/push-devices/unregister/',
    bearer: bearer,
    body: {'token': token, 'platform': platform, 'ownership_seq': ownershipSeq},
  );
}
