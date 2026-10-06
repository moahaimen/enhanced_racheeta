import 'package:dio/dio.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/json_reader.dart';
import '../../../core/api/page.dart';
import 'chat_models.dart';

/// The longest message the backend accepts (`ChatMessageCreateRequest.body`).
const int maxChatMessageLength = 2000;

/// Generic conversations (Phase 9B). The backend scopes everything to the caller's own
/// participations; another account's conversation is a plain 404.
class ChatApi {
  const ChatApi(this._client);
  final ApiClient _client;

  /// `GET /chat/conversations/` (latest activity first, paginated).
  Future<Page<Conversation>> conversations({
    int page = 1,
    int pageSize = 20,
    CancelToken? cancelToken,
  }) => _client.getPage<Conversation>(
    '/api/v1/chat/conversations/',
    parseItem: Conversation.fromJson,
    page: page,
    pageSize: pageSize,
    cancelToken: cancelToken,
  );

  /// `GET /chat/conversations/{id}/messages/`: page 1 is the LATEST page, later pages are older;
  /// messages inside each page are chronological.
  Future<Page<ChatMessage>> messages(
    String conversationId, {
    int page = 1,
    int pageSize = 20,
    CancelToken? cancelToken,
  }) => _client.getPage<ChatMessage>(
    '/api/v1/chat/conversations/${Uri.encodeComponent(conversationId)}/messages/',
    parseItem: ChatMessage.fromJson,
    page: page,
    pageSize: pageSize,
    cancelToken: cancelToken,
  );

  /// `POST /chat/conversations/{id}/messages/` `{body}` → the stored message. Never retried.
  Future<ChatMessage> send(
    String conversationId,
    String body, {
    CancelToken? cancelToken,
  }) => _client.post<ChatMessage>(
    '/api/v1/chat/conversations/${Uri.encodeComponent(conversationId)}/messages/',
    body: {'body': body},
    parse: ChatMessage.fromJson,
    cancelToken: cancelToken,
  );

  /// `POST /chat/conversations/{id}/read/` `{through_sequence}` → the stored read cursor.
  Future<int> markRead(
    String conversationId,
    int throughSequence, {
    CancelToken? cancelToken,
  }) => _client.post<int>(
    '/api/v1/chat/conversations/${Uri.encodeComponent(conversationId)}/read/',
    body: {'through_sequence': throughSequence},
    parse: (json) =>
        JsonReader.of(json, 'read state').integer('last_read_sequence'),
    cancelToken: cancelToken,
  );

  /// `GET /chat/unread-count/` (the authoritative count of unread messages from others).
  Future<int> unreadCount({CancelToken? cancelToken}) => _client.get<int>(
    '/api/v1/chat/unread-count/',
    parse: (json) => JsonReader.of(json, 'count').integer('count'),
    cancelToken: cancelToken,
  );

  /// `POST /chat/reservations/{id}/conversation` → the conversation for one of MY reservations
  /// (created on first use, the same one afterwards). Participants come from the reservation on
  /// the server, never from the client.
  Future<Conversation> openReservationConversation(
    String reservationId, {
    CancelToken? cancelToken,
  }) => _client.post<Conversation>(
    '/api/v1/chat/reservations/${Uri.encodeComponent(reservationId)}/conversation',
    body: const <String, Object?>{},
    parse: Conversation.fromJson,
    cancelToken: cancelToken,
  );
}
