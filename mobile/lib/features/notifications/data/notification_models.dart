import 'package:flutter/foundation.dart';

import '../../../core/api/json_reader.dart';

/// One persistent notification (`Notification` in the OpenAPI schema). `category`, `event_type` and
/// `resource_type` are kept as the raw codes: a value this app does not know yet (a future event)
/// must still be listed and readable, just not navigable. The raw `payload`, the recipient and the
/// dedupe key are never part of the client schema.
@immutable
class AppNotification {
  const AppNotification({
    required this.id,
    required this.category,
    required this.eventType,
    required this.title,
    required this.body,
    required this.resourceType,
    required this.resourceId,
    required this.isRead,
    required this.readAt,
    required this.createdAt,
  });

  factory AppNotification.fromJson(Object? json) {
    final r = JsonReader.of(json, 'notification');
    return AppNotification(
      id: r.string('id'),
      category: r.stringOr('category'),
      eventType: r.stringOr('event_type'),
      title: r.stringOr('title'),
      body: r.stringOr('body'),
      resourceType: r.stringOr('resource_type'),
      resourceId: r.stringOrNull('resource_id'),
      isRead: r.boolean('is_read'),
      readAt: r.instantOrNull('read_at'),
      createdAt: r.instant('created_at'),
    );
  }

  final String id;
  final String category;
  final String eventType;
  final String title;
  final String body;
  final String resourceType;
  final String? resourceId;
  final bool isRead;
  final DateTime? readAt;
  final DateTime createdAt;

  @override
  String toString() => 'AppNotification($eventType)'; // no content in logs
}

/// `{count: n}` (unread notifications or unread chat messages).
int parseCount(Object? json) => JsonReader.of(json, 'count').integer('count');

/// `{updated: n}` from "mark all read".
int parseUpdated(Object? json) =>
    JsonReader.of(json, 'mark all read').integer('updated');
