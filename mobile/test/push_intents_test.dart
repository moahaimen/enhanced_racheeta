import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/core/api/api_exception.dart';
import 'package:racheeta_mobile/features/auth/application/session_state.dart';
import 'package:racheeta_mobile/features/auth/data/auth_models.dart';
import 'package:racheeta_mobile/features/notifications/data/notification_models.dart';
import 'package:racheeta_mobile/features/push/push_intents.dart';
import 'package:racheeta_mobile/features/push/push_routes.dart';
import 'package:racheeta_mobile/features/push/push_source.dart';

import 'support/comms_support.dart';
import 'support/fake_backend.dart';
import 'support/provider_support.dart' show providerAccountJson;

Account _patient() => Account.fromJson(accountJson());
Account _provider() => Account.fromJson(providerAccountJson());

PushMessageData _chat([String? id = conversationId, String? messageId]) =>
    PushMessageData(
      messageId: messageId,
      data: {'type': 'chat_message', 'conversation_id': ?id},
    );

PushMessageData _note([String id = notificationId, String? messageId]) =>
    PushMessageData(
      messageId: messageId,
      data: {
        'type': 'notification',
        'notification_id': id,
        'event_type': 'RESERVATION_CREATED',
      },
    );

void main() {
  group('route mapping for a tapped push', () {
    test('a chat push opens that conversation; a notification push opens the centre', () {
      expect(routeForPush(_chat().data), '/chat/$conversationId');
      expect(routeForPush(_note().data), '/notifications');
    });

    test('unknown type, missing keys and malformed ids give no route and never throw', () {
      for (final data in <Map<String, String>>[
        {},
        {'type': 'something_new'},
        {'type': 'chat_message'},
        {'type': 'chat_message', 'conversation_id': 'not-a-uuid'},
        {'type': 'chat_message', 'conversation_id': '../../admin'},
        {'type': 'chat_message', 'conversation_id': 'javascript:alert(1)'},
        {'type': 'notification'},
        {'type': 'notification', 'notification_id': 'xyz'},
        {'conversation_id': conversationId},
      ]) {
        expect(routeForPush(data), isNull, reason: '$data');
      }
    });

    test('a url or custom scheme in the payload is never used as a route', () {
      expect(
        routeForPush({
          'type': 'chat_message',
          'conversation_id': 'https://evil.example/x',
          'route': 'https://evil.example',
        }),
        isNull,
      );
      expect(isValidId('${conversationId}extra'), isFalse);
      expect(isValidId(null), isFalse);
    });
  });

  group('route mapping for a notification row', () {
    AppNotification n({
      String event = 'RESERVATION_STATUS_CHANGED',
      String resource = 'RESERVATION',
      String? id = '44444444-4444-4444-8444-444444444444',
    }) => AppNotification.fromJson(
      notificationJson(event: event, resourceType: resource, resourceId: id),
    );

    test(
      'a patient and a provider each get their own side of the same event',
      () {
        expect(
          routeForNotification(n(), _patient()),
          '/reservations/44444444-4444-4444-8444-444444444444',
        );
        expect(
          routeForNotification(n(event: 'RESERVATION_CREATED'), _provider()),
          '/workspace/reservations/44444444-4444-4444-8444-444444444444',
        );
      },
    );

    test('unknown event, unknown resource, bad or missing id, or no capability: no route', () {
      expect(routeForNotification(n(event: 'NEW_THING'), _patient()), isNull);
      expect(routeForNotification(n(resource: 'JOB'), _patient()), isNull);
      expect(routeForNotification(n(id: 'nope'), _patient()), isNull);
      expect(routeForNotification(n(id: null), _patient()), isNull);
      final none = Account.fromJson({
        ...accountJson(),
        'permissions': <String>[],
      });
      expect(routeForNotification(n(), none), isNull);
    });
  });

  group('intent coordinator', () {
    late SessionState session;
    late List<String> routes;
    late DateTime clock;
    late PushIntentCoordinator coordinator;

    setUp(() {
      session = SessionAuthenticated(_patient());
      routes = <String>[];
      clock = DateTime.utc(2026, 10, 3, 9);
      coordinator = PushIntentCoordinator(
        session: () => session,
        navigate: routes.add,
        now: () => clock,
      );
    });

    test('a tap while signed in navigates once, to the validated route', () {
      coordinator.onOpened(_chat(conversationId, 'm1'));
      expect(routes, ['/chat/$conversationId']);
    });

    test('invalid or unknown pushes navigate nowhere', () {
      coordinator.onOpened(const PushMessageData(data: {}));
      coordinator.onOpened(_chat('bad'));
      coordinator.onOpened(const PushMessageData(data: {'type': 'x'}));
      expect(routes, isEmpty);
    });

    test(
      'the same Firebase message arriving by two callbacks is handled once',
      () {
        coordinator.onOpened(_chat(conversationId, 'm1'));
        coordinator.onOpened(_chat(conversationId, 'm1'));
        clock = clock.add(const Duration(minutes: 5));
        coordinator.onOpened(_chat(conversationId, 'm1'));
        expect(routes, hasLength(1));
      },
    );

    test('a push without an id is suppressed only briefly: a later new push for the same chat still works', () {
      coordinator.onOpened(_chat());
      clock = clock.add(const Duration(seconds: 1));
      coordinator.onOpened(_chat());
      expect(routes, hasLength(1), reason: 'duplicate within the window');
      clock = clock.add(const Duration(seconds: 30));
      coordinator.onOpened(_chat());
      expect(routes, hasLength(2), reason: 'a genuinely later tap');
    });

    test('different messages for the same conversation both navigate', () {
      coordinator.onOpened(_chat(conversationId, 'm1'));
      coordinator.onOpened(_chat(conversationId, 'm2'));
      expect(routes, hasLength(2));
    });

    test('cold start: held while restoring, delivered once when signed in', () {
      session = const SessionRestoring();
      coordinator.onOpened(_chat(conversationId, 'cold'));
      expect(routes, isEmpty);
      coordinator.onSessionChanged();
      expect(routes, isEmpty, reason: 'still restoring');
      session = SessionAuthenticated(_patient());
      coordinator.onSessionChanged();
      expect(routes, ['/chat/$conversationId']);
      coordinator.onSessionChanged();
      expect(routes, hasLength(1), reason: 'never replayed');
    });

    test(
      'an offline restore failure keeps holding until the session resolves',
      () {
        session = const SessionRestoreFailed(ApiException.network);
        coordinator.onOpened(_note(notificationId, 'n1'));
        coordinator.onSessionChanged();
        expect(routes, isEmpty);
        session = SessionAuthenticated(_patient());
        coordinator.onSessionChanged();
        expect(routes, ['/notifications']);
      },
    );

    test('a signed-out user is never navigated, and the tap is not replayed after a later sign-in', () {
      session = const SessionAnonymous();
      coordinator.onOpened(_chat(conversationId, 'out'));
      expect(routes, isEmpty);
      session = SessionAuthenticated(_patient());
      coordinator.onSessionChanged();
      expect(routes, isEmpty);
    });

    test(
      'a tap held during restore is dropped if the session ends signed out',
      () {
        session = const SessionRestoring();
        coordinator.onOpened(_chat(conversationId, 'held'));
        session = const SessionAnonymous();
        coordinator.onSessionChanged();
        session = SessionAuthenticated(_provider());
        coordinator.onSessionChanged();
        expect(routes, isEmpty, reason: 'never reaches another account');
      },
    );
  });
}
