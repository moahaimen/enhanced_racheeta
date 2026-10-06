import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/app/app.dart';
import 'package:racheeta_mobile/features/push/push_registration.dart';
import 'package:racheeta_mobile/features/push/push_source.dart';

import 'support/comms_support.dart';
import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart' show switchAccountTo;

const _convs = '/api/v1/chat/conversations/';
const _unreadChat = '/api/v1/chat/unread-count/';
const _unreadNote = '/api/v1/notifications/unread-count/';
const _notes = '/api/v1/notifications/';
const _msgs = '/api/v1/chat/conversations/$conversationId/messages/';
const _read = '/api/v1/chat/conversations/$conversationId/read/';
const _tall = Size(800, 2400);

void _comms(FakeBackend b, {void Function()? onMessages}) => b
  ..on(
    'GET',
    _convs,
    (_) => FakeBackend.json(200, pageJson([conversationJson()])),
  )
  ..on('GET', _unreadChat, (_) => FakeBackend.json(200, {'count': 0}))
  ..on('GET', _unreadNote, (_) => FakeBackend.json(200, {'count': 0}))
  ..on(
    'GET',
    _notes,
    (_) => FakeBackend.json(200, pageJson([notificationJson()])),
  )
  ..on('GET', _msgs, (_) {
    onMessages?.call();
    return FakeBackend.json(
      200,
      pageJson([messageJson(sequence: 1, body: 'hello from them')]),
    );
  })
  ..on('POST', _read, (_) => FakeBackend.json(200, {'last_read_sequence': 1}))
  ..on(
    'POST',
    '/api/v1/notifications/push-devices/',
    (_) => FakeBackend.json(200, {
      'id': 'f1',
      'platform': 'ANDROID',
      'is_active': true,
      'last_registered_at': '2026-10-03T08:00:00Z',
    }),
  );

PushMessageData _chatPush([String? messageId]) => PushMessageData(
  messageId: messageId,
  data: {'type': 'chat_message', 'conversation_id': conversationId},
);

void main() {
  group('while the app is running', () {
    testWidgets(
      'a foreground push only refreshes backend state (counts, lists, the open thread)',
      (tester) async {
        final source = FakePushSource();
        final h = await pumpPatientApp(
          tester,
          path: '/chat/$conversationId',
          size: _tall,
          overrides: [pushSourceProvider.overrideWithValue(source)],
          script: _comms,
        );
        final msgs = h.backend.count('GET', _msgs);
        final notes = h.backend.count('GET', _unreadNote);
        final convs = h.backend.count('GET', _convs);
        source.foreground.add(_chatPush('f1'));
        await tester.pumpAndSettle();
        expect(h.backend.count('GET', _msgs), msgs + 1);
        expect(h.backend.count('GET', _convs), greaterThan(convs));
        // notification state is refreshed too, but nothing navigates and nothing is stored locally
        expect(
          h.backend.count('GET', _unreadNote),
          greaterThanOrEqualTo(notes),
        );
        expect(find.text('hello from them'), findsOneWidget);
      },
    );

    testWidgets(
      'a push for a thread that is not open does not create or fetch it',
      (tester) async {
        final source = FakePushSource();
        final h = await pumpPatientApp(
          tester,
          size: _tall,
          overrides: [pushSourceProvider.overrideWithValue(source)],
          script: _comms,
        );
        source.foreground.add(_chatPush('f2'));
        await tester.pumpAndSettle();
        expect(h.backend.count('GET', _msgs), 0);
        expect(
          find.byKey(const Key('home-greeting')),
          findsOneWidget,
          reason: 'no navigation',
        );
      },
    );

    testWidgets(
      'a background tap opens the conversation exactly once even if delivered twice',
      (tester) async {
        final source = FakePushSource();
        final h = await pumpPatientApp(
          tester,
          size: _tall,
          overrides: [pushSourceProvider.overrideWithValue(source)],
          script: _comms,
        );
        source.opened.add(_chatPush('tap-1'));
        source.opened.add(_chatPush('tap-1'));
        await tester.pumpAndSettle();
        expect(h.backend.count('GET', _msgs), 1);
        expect(find.text('hello from them'), findsOneWidget);
      },
    );

    testWidgets('a notification push opens the notification centre', (
      tester,
    ) async {
      final source = FakePushSource();
      final h = await pumpPatientApp(
        tester,
        size: _tall,
        overrides: [pushSourceProvider.overrideWithValue(source)],
        script: _comms,
      );
      source.opened.add(
        PushMessageData(
          messageId: 'n1',
          data: {
            'type': 'notification',
            'notification_id': notificationId,
            'event_type': 'RESERVATION_CREATED',
          },
        ),
      );
      await tester.pumpAndSettle();
      expect(h.backend.count('GET', _notes), greaterThanOrEqualTo(1));
      expect(find.text('Reservation confirmed'), findsOneWidget);
    });

    testWidgets('a malformed or unknown push is ignored', (tester) async {
      final source = FakePushSource();
      final h = await pumpPatientApp(
        tester,
        size: _tall,
        overrides: [pushSourceProvider.overrideWithValue(source)],
        script: _comms,
      );
      source.opened.add(
        const PushMessageData(
          data: {'type': 'chat_message', 'conversation_id': '../../x'},
        ),
      );
      source.opened.add(const PushMessageData(data: {'type': 'brand_new'}));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('home-greeting')), findsOneWidget);
      expect(h.backend.count('GET', _msgs), 0);
    });

    testWidgets(
      'a tap leads to the same screen gates: another account gets the generic not-found',
      (tester) async {
        final source = FakePushSource();
        final h = await pumpPatientApp(
          tester,
          size: _tall,
          overrides: [pushSourceProvider.overrideWithValue(source)],
          script: (b) {
            _comms(b);
            b.on('GET', _msgs, (_) => FakeBackend.error(404, 'not_found'));
          },
        );
        source.opened.add(_chatPush('gated'));
        await tester.pumpAndSettle();
        expect(find.text("We couldn't find that."), findsOneWidget);
        expect(h.backend.count('GET', _msgs), 1);
      },
    );

    testWidgets(
      'a push tapped under A is not routed after the app switched to B',
      (tester) async {
        final source = FakePushSource();
        final h = await pumpPatientApp(
          tester,
          size: _tall,
          overrides: [pushSourceProvider.overrideWithValue(source)],
          script: _comms,
        );
        await switchAccountTo(
          tester,
          h,
          accountJson(
            id: '99999999-9999-4999-8999-999999999999',
            name: 'Patient B',
          ),
        );
        // B is signed in: the tap is evaluated against B's session, never A's
        source.opened.add(_chatPush('after-switch'));
        await tester.pumpAndSettle();
        expect(h.backend.count('GET', _msgs), 1);
      },
    );
  });

  group('cold start', () {
    Future<Harness> boot(
      WidgetTester tester,
      FakePushSource source, {
      required bool signedIn,
      Completer<void>? meGate,
    }) async {
      tester.view.physicalSize = _tall;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final h = Harness(
        storedRefresh: signedIn ? 'r1' : null,
        autoRestore: true,
        language: 'en',
        extraOverrides: [
          ...clockOverrides,
          pushSourceProvider.overrideWithValue(source),
        ],
      );
      addTearDown(h.dispose);
      h.backend
        ..on(
          'POST',
          '/api/v1/auth/refresh',
          (_) => FakeBackend.json(200, tokens('a2', 'r2')),
        )
        ..on('GET', '/api/v1/me', (_) async {
          if (meGate != null) await meGate.future;
          return FakeBackend.json(200, accountJson());
        });
      _comms(h.backend);
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: h.container,
          child: const RacheetaApp(),
        ),
      );
      return h;
    }

    testWidgets(
      'the launching push waits for the session to be restored, then navigates once',
      (tester) async {
        final gate = Completer<void>();
        final source = FakePushSource()..initial = _chatPush('cold-1');
        final h = await boot(tester, source, signedIn: true, meGate: gate);
        await tester.pump(const Duration(milliseconds: 200));
        expect(
          h.backend.count('GET', _msgs),
          0,
          reason: 'still restoring: nothing private yet',
        );
        gate.complete();
        await tester.pumpAndSettle();
        expect(h.backend.count('GET', _msgs), 1);
        expect(find.text('hello from them'), findsOneWidget);
        // opening it again from another callback does not navigate a second time
        source.opened.add(_chatPush('cold-1'));
        await tester.pumpAndSettle();
        expect(h.backend.count('GET', _msgs), 1);
      },
    );

    testWidgets(
      'signed out: the launching push never opens a private screen and is not replayed',
      (tester) async {
        final source = FakePushSource()..initial = _chatPush('cold-2');
        final h = await boot(tester, source, signedIn: false);
        await tester.pumpAndSettle();
        expect(h.backend.count('GET', _msgs), 0);
        expect(find.byKey(const Key('home-greeting')), findsNothing);
        expect(find.text('Sign in'), findsWidgets);
      },
    );
  });

  testWidgets(
    'without Firebase configuration the app runs with push disabled',
    (tester) async {
      final h = await pumpPatientApp(tester, size: _tall, script: _comms);
      expect(h.backend.count('POST', '/api/v1/notifications/push-devices/'), 0);
      expect(find.byKey(const Key('home-greeting')), findsOneWidget);
    },
  );
}
