import 'dart:async';

import 'package:racheeta_mobile/features/push/push_source.dart';

const notificationId = 'aaaa1111-0000-4000-8000-000000000001';
const conversationId = 'cccc1111-0000-4000-8000-000000000001';
const messageId = 'dddd1111-0000-4000-8000-000000000001';
const otherAccountId = 'eeee1111-0000-4000-8000-000000000001';

/// A `Notification` (the client view; no payload, recipient or dedupe key).
Map<String, Object?> notificationJson({
  String id = notificationId,
  String event = 'RESERVATION_STATUS_CHANGED',
  String category = 'RESERVATION',
  String resourceType = 'RESERVATION',
  String? resourceId = '44444444-4444-4444-8444-444444444444',
  bool isRead = false,
  String title = 'Reservation confirmed',
  String body = 'Open Racheeta to view the details.',
  String createdAt = '2026-10-03T08:00:00Z',
}) => {
  'id': id,
  'category': category,
  'event_type': event,
  'title': title,
  'body': body,
  'resource_type': resourceType,
  'resource_id': resourceId,
  'is_read': isRead,
  'read_at': isRead ? '2026-10-03T08:30:00Z' : null,
  'created_at': createdAt,
};

Map<String, Object?> chatAccountJson({
  String id = otherAccountId,
  String name = 'Dr. Sara Ahmed',
  String role = 'PROVIDER',
}) => {'id': id, 'full_name': name, 'role': role};

Map<String, Object?> conversationJson({
  String id = conversationId,
  String name = 'Dr. Sara Ahmed',
  String role = 'PROVIDER',
  String contextType = 'RESERVATION',
  int unread = 0,
  int lastSequence = 3,
  int lastRead = 3,
  String? lastMessageAt = '2026-10-03T08:00:00Z',
}) => {
  'id': id,
  'context_type': contextType,
  'context_id': '44444444-4444-4444-8444-444444444444',
  'other_participant': chatAccountJson(name: name, role: role),
  'last_sequence': lastSequence,
  'last_read_sequence': lastRead,
  'unread_count': unread,
  'last_message_at': lastMessageAt,
  'created_at': '2026-10-02T08:00:00Z',
};

Map<String, Object?> messageJson({
  required int sequence,
  bool mine = false,
  String? body,
  String sender = 'Dr. Sara Ahmed',
  String? id,
}) => {
  'id': id ?? 'dddd0000-0000-4000-8000-${sequence.toString().padLeft(12, '0')}',
  'sequence': sequence,
  'sender': chatAccountJson(name: mine ? 'Layla Hassan' : sender),
  'is_mine': mine,
  'body': body ?? 'message $sequence',
  'created_at': '2026-10-03T08:0$sequence:00Z',
};

/// A scriptable Firebase Messaging stand-in: no Firebase, no network.
class FakePushSource implements PushSource {
  FakePushSource({
    this.available = true,
    this.currentPermission = PushPermission.granted,
    this.fixedToken = 'fake-fcm-token-1',
  });

  bool available;
  PushPermission currentPermission;
  PushPermission permissionAfterRequest = PushPermission.granted;
  String? fixedToken;

  /// When set, `token()` waits for it (simulates a slow token issue).
  Completer<String?>? tokenGate;
  int tokenCalls = 0;
  int permissionRequests = 0;
  PushMessageData? initial;

  final StreamController<String> refreshes =
      StreamController<String>.broadcast();
  final StreamController<PushMessageData> foreground =
      StreamController<PushMessageData>.broadcast();
  final StreamController<PushMessageData> opened =
      StreamController<PushMessageData>.broadcast();

  @override
  bool get isAvailable => available;

  @override
  Future<PushPermission> permission() async => currentPermission;

  @override
  Future<PushPermission> requestPermission() async {
    permissionRequests++;
    currentPermission = permissionAfterRequest;
    return currentPermission;
  }

  @override
  Future<String?> token() {
    tokenCalls++;
    final gate = tokenGate;
    return gate != null ? gate.future : Future<String?>.value(fixedToken);
  }

  @override
  Stream<String> get tokenRefreshes => refreshes.stream;

  @override
  Stream<PushMessageData> get foregroundMessages => foreground.stream;

  @override
  Stream<PushMessageData> get openedMessages => opened.stream;

  @override
  Future<PushMessageData?> initialMessage() async => initial;
}
