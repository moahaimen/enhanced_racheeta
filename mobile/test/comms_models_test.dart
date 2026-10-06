import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/features/chat/data/chat_models.dart';
import 'package:racheeta_mobile/features/notifications/data/notification_models.dart';
import 'package:racheeta_mobile/features/push/firebase_push_source.dart';
import 'package:racheeta_mobile/features/push/push_source.dart';

import 'support/comms_support.dart';

void main() {
  group('AppNotification', () {
    test('parses, keeping unknown codes raw and instants in UTC', () {
      final n = AppNotification.fromJson(
        notificationJson(
          event: 'FUTURE_EVENT',
          category: 'FUTURE',
          resourceType: 'THING',
        ),
      );
      expect(n.eventType, 'FUTURE_EVENT');
      expect(n.category, 'FUTURE');
      expect(n.resourceType, 'THING');
      expect(n.createdAt.isUtc, isTrue);
      expect(n.isRead, isFalse);
      expect(n.readAt, isNull);
      expect(n.toString(), isNot(contains('Reservation confirmed')));
    });

    test(
      'a read notification has its read time; a null resource id stays null',
      () {
        final n = AppNotification.fromJson(
          notificationJson(isRead: true, resourceId: null),
        );
        expect(n.isRead, isTrue);
        expect(n.readAt, isNotNull);
        expect(n.resourceId, isNull);
      },
    );

    test(
      'missing id / is_read / a timestamp without an offset are format errors',
      () {
        expect(
          () => AppNotification.fromJson({...notificationJson()}..remove('id')),
          throwsFormatException,
        );
        expect(
          () => AppNotification.fromJson(
            {...notificationJson()}..remove('is_read'),
          ),
          throwsFormatException,
        );
        expect(
          () => AppNotification.fromJson({
            ...notificationJson(),
            'created_at': '2026-10-03T08:00:00',
          }),
          throwsFormatException,
        );
        expect(() => AppNotification.fromJson('nope'), throwsFormatException);
      },
    );

    test('counts parse strictly', () {
      expect(parseCount({'count': 3}), 3);
      expect(parseUpdated({'updated': 0}), 0);
      expect(() => parseCount({'count': '3'}), throwsFormatException);
      expect(() => parseUpdated({}), throwsFormatException);
    });
  });

  group('Conversation and ChatMessage', () {
    test('a conversation parses; context type stays raw; unread comes from the backend', () {
      final c = Conversation.fromJson(
        conversationJson(contextType: 'FUTURE', unread: 3),
      );
      expect(c.contextType, 'FUTURE');
      expect(c.unreadCount, 3);
      expect(c.hasUnread, isTrue);
      expect(c.other.fullName, 'Dr. Sara Ahmed');
      expect(c.lastMessageAt!.isUtc, isTrue);
      expect(
        Conversation.fromJson(conversationJson(lastMessageAt: null))
            .lastMessageAt,
        isNull,
      );
    });

    test('required conversation keys are strict', () {
      for (final key in [
        'id',
        'other_participant',
        'last_sequence',
        'unread_count',
        'created_at',
      ]) {
        expect(
          () => Conversation.fromJson({...conversationJson()}..remove(key)),
          throwsFormatException,
          reason: key,
        );
      }
    });

    test('a message keeps the backend verdict on authorship and never prints its body', () {
      final mine = ChatMessage.fromJson(
        messageJson(sequence: 2, mine: true, body: 'secret text'),
      );
      final theirs = ChatMessage.fromJson(messageJson(sequence: 3));
      expect(mine.isMine, isTrue);
      expect(theirs.isMine, isFalse);
      expect(mine.sequence, 2);
      expect(mine.toString(), isNot(contains('secret text')));
      expect(
        () => ChatMessage.fromJson(
          {...messageJson(sequence: 1)}..remove('is_mine'),
        ),
        throwsFormatException,
      );
      expect(
        () =>
            ChatMessage.fromJson({...messageJson(sequence: 1)}..remove('body')),
        throwsFormatException,
      );
      expect(
        () => ChatMessage.fromJson(
          {...messageJson(sequence: 1)}..remove('sender'),
        ),
        throwsFormatException,
      );
    });
  });

  group('push configuration', () {
    test(
      'without --dart-define Firebase values the build has push disabled',
      () async {
        expect(FirebaseConfig.fromEnvironment(), isNull);
        final source = await createPushSource(null);
        expect(source.isAvailable, isFalse);
        expect(await source.token(), isNull);
        expect(await source.initialMessage(), isNull);
        expect(await source.permission(), PushPermission.denied);
      },
    );
  });
}
