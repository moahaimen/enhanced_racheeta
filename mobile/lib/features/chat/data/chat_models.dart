import 'package:flutter/foundation.dart';

import '../../../core/api/json_reader.dart';

/// The only account fields a conversation exposes about a participant.
@immutable
class ChatAccount {
  const ChatAccount({
    required this.id,
    required this.fullName,
    required this.role,
  });

  factory ChatAccount.fromJson(Object? json) {
    final r = JsonReader.of(json, 'chat account');
    return ChatAccount(
      id: r.string('id'),
      fullName: r.stringOr('full_name'),
      role: r.stringOr('role'),
    );
  }

  final String id;
  final String fullName;
  final String role;
}

/// One of the signed-in account's conversations (`ChatConversation`). `context_type` is kept as
/// the raw code (only `RESERVATION` exists today; a future context renders a generic label).
@immutable
class Conversation {
  const Conversation({
    required this.id,
    required this.contextType,
    required this.contextId,
    required this.other,
    required this.lastSequence,
    required this.lastReadSequence,
    required this.unreadCount,
    required this.lastMessageAt,
    required this.createdAt,
  });

  factory Conversation.fromJson(Object? json) {
    final r = JsonReader.of(json, 'conversation');
    return Conversation(
      id: r.string('id'),
      contextType: r.stringOr('context_type'),
      contextId: r.stringOr('context_id'),
      other: ChatAccount.fromJson(r.raw('other_participant')),
      lastSequence: r.integer('last_sequence'),
      lastReadSequence: r.integer('last_read_sequence'),
      unreadCount: r.integer('unread_count'),
      lastMessageAt: r.instantOrNull('last_message_at'),
      createdAt: r.instant('created_at'),
    );
  }

  final String id;
  final String contextType;
  final String contextId;
  final ChatAccount other;
  final int lastSequence;
  final int lastReadSequence;
  final int unreadCount;
  final DateTime? lastMessageAt;
  final DateTime createdAt;

  bool get hasUnread => unreadCount > 0;
}

/// One immutable text message. `is_mine` is the backend's verdict on authorship (never inferred
/// from ids on the device); `sequence` is the per-conversation order.
@immutable
class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.sequence,
    required this.sender,
    required this.isMine,
    required this.body,
    required this.createdAt,
  });

  factory ChatMessage.fromJson(Object? json) {
    final r = JsonReader.of(json, 'message');
    return ChatMessage(
      id: r.string('id'),
      sequence: r.integer('sequence'),
      sender: ChatAccount.fromJson(r.raw('sender')),
      isMine: r.boolean('is_mine'),
      body: r.string('body'),
      createdAt: r.instant('created_at'),
    );
  }

  final String id;
  final int sequence;
  final ChatAccount sender;
  final bool isMine;
  final String body;
  final DateTime createdAt;

  @override
  String toString() => 'ChatMessage($sequence)'; // never the body
}
