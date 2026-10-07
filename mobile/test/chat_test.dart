import 'dart:async';

import 'package:dio/dio.dart' show ResponseBody;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/comms_support.dart';
import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart'
    show providerAccountJson, providerReservationJson, switchAccountTo;

const _convs = '/api/v1/chat/conversations/';
const _unread = '/api/v1/chat/unread-count/';
String _msgs([String id = conversationId]) =>
    '/api/v1/chat/conversations/$id/messages/';
String _readPath([String id = conversationId]) =>
    '/api/v1/chat/conversations/$id/read/';
const _tall = Size(800, 2400);
const _phone = Size(360, 780);

final Map<String, Object?> _b = accountJson(
  id: '99999999-9999-4999-8999-999999999999',
  name: 'Patient B',
);

ResponseBody _validation(String code) => FakeBackend.json(400, {
  'error': {
    'code': 'validation_error',
    'message': 'Server wrote this: secret detail',
    'details': {
      'body': ['server text'],
    },
    'codes': {
      'body': [code],
    },
  },
});

/// A thread whose messages 1..3 are chronological, with 2 from the other side.
void _thread(
  FakeBackend b, {
  List<Map<String, Object?>>? latest,
  String? older,
  Responder? send,
}) {
  b.on(
    'GET',
    _convs,
    (_) => FakeBackend.json(200, pageJson([conversationJson()])),
  );
  b.on('GET', _unread, (_) => FakeBackend.json(200, {'count': 0}));
  b.on('GET', _msgs(), (r) {
    if (r.query['page'] == 2) {
      return FakeBackend.json(
        200,
        pageJson([messageJson(sequence: 0, body: 'older zero')], count: 5),
      );
    }
    return FakeBackend.json(
      200,
      pageJson(
        latest ??
            [
              messageJson(sequence: 1, mine: true, body: 'first mine'),
              messageJson(sequence: 2, body: 'second theirs'),
              messageJson(sequence: 3, mine: true, body: 'third mine'),
            ],
        count: older == null ? 3 : 5,
        next: older,
      ),
    );
  });
  b.on(
    'POST',
    _readPath(),
    (_) => FakeBackend.json(200, {'last_read_sequence': 3}),
  );
  if (send != null) b.on('POST', _msgs(), send);
}

void main() {
  group('conversation list', () {
    testWidgets(
      'lists the other party, role, context, time and an unread badge',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/chat',
          size: _tall,
          script: (b) {
            b.on(
              'GET',
              _convs,
              (_) => FakeBackend.json(
                200,
                pageJson([
                  conversationJson(unread: 2, lastSequence: 5, lastRead: 3),
                  conversationJson(
                    id: 'cccc1111-0000-4000-8000-000000000002',
                    name: 'Future Co',
                    role: 'FUTURE_ROLE',
                    contextType: 'FUTURE_CONTEXT',
                  ),
                ]),
              ),
            );
            b.on('GET', _unread, (_) => FakeBackend.json(200, {'count': 2}));
          },
        );
        expect(find.text('Dr. Sara Ahmed'), findsOneWidget);
        expect(find.textContaining('Reservation conversation'), findsOneWidget);
        expect(
          find.byKey(const Key('unread-badge-$conversationId')),
          findsOneWidget,
        );
        // unknown role / context degrade to neutral labels, nothing crashes
        expect(find.text('Future Co'), findsOneWidget);
        expect(find.textContaining('Conversation'), findsWidgets);
        expect(find.textContaining('11:00'), findsWidgets);
        expect(tester.takeException(), isNull);
      },
    );

    testWidgets('pagination keeps rows when the next page fails', (
      tester,
    ) async {
      var fail = true;
      await pumpPatientApp(
        tester,
        path: '/chat',
        size: _tall,
        script: (b) => b.on('GET', _convs, (r) {
          if (r.query['page'] == 2) {
            return fail
                ? FakeBackend.error(500, 'server_error')
                : FakeBackend.json(
                    200,
                    pageJson([
                      conversationJson(
                        id: 'cccc1111-0000-4000-8000-000000000002',
                        name: 'Second Person',
                      ),
                    ], count: 2),
                  );
          }
          return FakeBackend.json(
            200,
            pageJson(
              [conversationJson(name: 'First Person')],
              count: 2,
              next: 'https://api.test/x?page=2',
            ),
          );
        }),
      );
      await tester.tap(find.text('Load more'));
      await tester.pumpAndSettle();
      expect(find.text('Could not load more results.'), findsOneWidget);
      expect(find.text('First Person'), findsOneWidget);
      fail = false;
      await tester.tap(find.text('Load more'));
      await tester.pumpAndSettle();
      expect(find.text('Second Person'), findsOneWidget);
    });

    testWidgets('empty state and a safe error with retry', (tester) async {
      var fail = true;
      await pumpPatientApp(
        tester,
        path: '/chat',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _convs,
          (_) => fail
              ? FakeBackend.error(500, 'server_error', message: 'Traceback')
              : FakeBackend.json(200, pageJson(<Object?>[])),
        ),
      );
      expect(find.textContaining('Traceback'), findsNothing);
      fail = false;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('No conversations yet'), findsOneWidget);
    });

    testWidgets('Arabic right-to-left at phone width', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/chat',
        size: _phone,
        language: 'ar',
        script: (b) => b.on(
          'GET',
          _convs,
          (_) => FakeBackend.json(200, pageJson([conversationJson(unread: 1)])),
        ),
      );
      expect(find.text('الرسائل'), findsWidgets);
      expect(find.textContaining('محادثة حجز'), findsOneWidget);
      expect(
        Directionality.of(tester.element(find.text('Dr. Sara Ahmed'))),
        TextDirection.rtl,
      );
      expect(tester.takeException(), isNull);
    });
  });

  group('conversation', () {
    testWidgets(
      'messages appear in the backend order; own and counterpart sides are right',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/chat/$conversationId',
          size: _phone,
          script: _thread,
        );
        final first = tester.getCenter(find.text('first mine'));
        final second = tester.getCenter(find.text('second theirs'));
        final third = tester.getCenter(find.text('third mine'));
        // chronological: oldest at the top, newest at the bottom
        expect(first.dy, lessThan(second.dy));
        expect(second.dy, lessThan(third.dy));
        // left-to-right: own messages on the right (end), the other party's on the left (start)
        expect(first.dx, greaterThan(second.dx));
        expect(third.dx, greaterThan(second.dx));
        expect(
          find.text('Dr. Sara Ahmed'),
          findsWidgets,
          reason: 'header from the thread',
        );
      },
    );

    testWidgets(
      'right-to-left keeps authorship: own is still the end side (now left)',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/chat/$conversationId',
          size: _phone,
          language: 'ar',
          script: _thread,
        );
        final mine = tester.getCenter(find.text('first mine'));
        final theirs = tester.getCenter(find.text('second theirs'));
        expect(mine.dx, lessThan(theirs.dx));
        expect(find.text('إرسال'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );

    testWidgets(
      'older messages are fetched as page 2 and prepended without moving the reader',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/chat/$conversationId',
          size: _phone,
          script: (b) => _thread(b, older: 'https://api.test/x?page=2'),
        );
        expect(
          h.backend.to('GET', _msgs()).first.query.containsKey('page'),
          isFalse,
        );
        final before = tester.getCenter(find.text('third mine'));
        await tester.ensureVisible(find.byKey(const Key('load-older')));
        await tester.tap(find.byKey(const Key('load-older')));
        await tester.pumpAndSettle();
        expect(h.backend.to('GET', _msgs()).last.query['page'], 2);
        expect(find.text('older zero'), findsOneWidget);
        expect(tester.getCenter(find.text('third mine')), before);
        expect(
          tester.getCenter(find.text('older zero')).dy,
          lessThan(tester.getCenter(find.text('first mine')).dy),
        );
      },
    );

    testWidgets('a failed older page keeps what is shown', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/chat/$conversationId',
        size: _phone,
        script: (b) {
          _thread(b, older: 'https://api.test/x?page=2');
          b.on('GET', _msgs(), (r) {
            if (r.query['page'] == 2) {
              return FakeBackend.error(500, 'server_error');
            }
            return FakeBackend.json(
              200,
              pageJson(
                [messageJson(sequence: 3, body: 'newest')],
                count: 5,
                next: 'https://api.test/x?page=2',
              ),
            );
          });
        },
      );
      await tester.ensureVisible(find.byKey(const Key('load-older')));
      await tester.tap(find.byKey(const Key('load-older')));
      await tester.pumpAndSettle();
      expect(find.text("Couldn't load earlier messages."), findsOneWidget);
      expect(find.text('newest'), findsOneWidget);
    });

    testWidgets(
      'a conversation of someone else is the generic not-found text',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/chat/$conversationId',
          size: _phone,
          script: (b) => b
            ..on(
              'GET',
              _convs,
              (_) => FakeBackend.json(200, pageJson(<Object?>[])),
            )
            ..on('GET', _msgs(), (_) => FakeBackend.error(404, 'not_found')),
        );
        expect(find.text("We couldn't find that."), findsOneWidget);
      },
    );

    testWidgets('an empty thread says so', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/chat/$conversationId',
        size: _phone,
        script: (b) => _thread(b, latest: const []),
      );
      expect(find.text('No messages yet. Say hello.'), findsOneWidget);
    });
  });

  group('read semantics', () {
    testWidgets(
      'the loaded thread is marked read through its newest sequence, once',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/chat/$conversationId',
          size: _phone,
          script: _thread,
        );
        final posts = h.backend.to('POST', _readPath());
        expect(posts, hasLength(1));
        expect(posts.single.body, {'through_sequence': 3});
        // the list and the count are reloaded from the backend afterwards
        expect(h.backend.count('GET', _unread), greaterThanOrEqualTo(1));
      },
    );

    testWidgets('a thread with only my own messages sends no read request', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/chat/$conversationId',
        size: _phone,
        script: (b) => _thread(
          b,
          latest: [messageJson(sequence: 1, mine: true, body: 'only mine')],
        ),
      );
      expect(h.backend.count('POST', _readPath()), 0);
    });

    testWidgets('a failed read is not retried', (tester) async {
      final h = await pumpPatientApp(
        tester,
        path: '/chat/$conversationId',
        size: _phone,
        script: (b) {
          _thread(b);
          b.on(
            'POST',
            _readPath(),
            (_) => FakeBackend.error(500, 'server_error'),
          );
        },
      );
      await tester.pump(const Duration(seconds: 30));
      expect(h.backend.count('POST', _readPath()), 1);
    });
  });

  group('sending', () {
    Future<Harness> open(WidgetTester tester, {Responder? send}) =>
        pumpPatientApp(
          tester,
          path: '/chat/$conversationId',
          size: _phone,
          script: (b) => _thread(
            b,
            send:
                send ??
                (r) => FakeBackend.json(
                  201,
                  messageJson(sequence: 4, mine: true, body: 'hello there'),
                ),
          ),
        );

    testWidgets(
      'one tap is one POST with the trimmed text; the thread and list reload',
      (tester) async {
        final h = await open(tester);
        final listsBefore = h.backend.count('GET', _convs);
        await tester.enterText(
          find.byKey(const Key('composer-field')),
          '  hello there  ',
        );
        await tester.pump();
        await tester.tap(find.byKey(const Key('composer-send')));
        await tester.pumpAndSettle();
        final posts = h.backend.to('POST', _msgs());
        expect(posts, hasLength(1));
        expect(posts.single.body, {'body': 'hello there'});
        expect(find.text('hello there'), findsOneWidget);
        expect(
          tester
              .widget<TextField>(find.byKey(const Key('composer-field')))
              .controller!
              .text,
          isEmpty,
        );
        expect(h.backend.count('GET', _convs), greaterThan(listsBefore));
      },
    );

    testWidgets('a blank draft cannot be sent', (tester) async {
      final h = await open(tester);
      expect(
        tester
            .widget<FilledButton>(
              find.descendant(
                of: find.byKey(const Key('composer-send')),
                matching: find.byType(FilledButton),
              ),
            )
            .onPressed,
        isNull,
      );
      await tester.enterText(find.byKey(const Key('composer-field')), '    ');
      await tester.pump();
      expect(
        tester
            .widget<FilledButton>(
              find.descendant(
                of: find.byKey(const Key('composer-send')),
                matching: find.byType(FilledButton),
              ),
            )
            .onPressed,
        isNull,
      );
      expect(h.backend.count('POST', _msgs()), 0);
    });

    testWidgets('over 2000 characters is refused before any request', (
      tester,
    ) async {
      final h = await open(tester);
      await tester.enterText(
        find.byKey(const Key('composer-field')),
        'x' * 2001,
      );
      await tester.pump();
      await tester.tap(find.byKey(const Key('composer-send')));
      await tester.pumpAndSettle();
      expect(
        find.text('A message can be at most 2000 characters.'),
        findsOneWidget,
      );
      expect(h.backend.count('POST', _msgs()), 0);
    });

    testWidgets('exactly 2000 characters is sent', (tester) async {
      final h = await open(tester);
      await tester.enterText(
        find.byKey(const Key('composer-field')),
        'y' * 2000,
      );
      await tester.pump();
      await tester.tap(find.byKey(const Key('composer-send')));
      await tester.pumpAndSettle();
      expect(h.backend.to('POST', _msgs()), hasLength(1));
    });

    testWidgets(
      'a failed send keeps the draft, shows a fixed message and is never retried',
      (tester) async {
        final h = await open(
          tester,
          send: (_) =>
              FakeBackend.error(500, 'server_error', message: 'raw db error'),
        );
        await tester.enterText(
          find.byKey(const Key('composer-field')),
          'keep me',
        );
        await tester.pump();
        await tester.tap(find.byKey(const Key('composer-send')));
        await tester.pumpAndSettle();
        expect(find.textContaining('raw db error'), findsNothing);
        expect(find.byKey(const Key('composer-error')), findsOneWidget);
        expect(
          tester
              .widget<TextField>(find.byKey(const Key('composer-field')))
              .controller!
              .text,
          'keep me',
        );
        await tester.pump(const Duration(seconds: 30));
        expect(h.backend.count('POST', _msgs()), 1);
      },
    );

    for (final c in [
      ('blank', 'Write a message first.'),
      ('max_length', 'A message can be at most 2000 characters.'),
    ]) {
      testWidgets(
        'the server\'s ${c.$1} code maps to fixed text, not the server message',
        (tester) async {
          await open(tester, send: (_) => _validation(c.$1));
          await tester.enterText(find.byKey(const Key('composer-field')), 'hi');
          await tester.pump();
          await tester.tap(find.byKey(const Key('composer-send')));
          await tester.pumpAndSettle();
          expect(find.text(c.$2), findsOneWidget);
          expect(find.textContaining('secret detail'), findsNothing);
          expect(find.textContaining('server text'), findsNothing);
        },
      );
    }

    testWidgets('a duplicate tap while sending sends one request', (
      tester,
    ) async {
      final gate = Completer<void>();
      final h = await open(
        tester,
        send: (_) async {
          await gate.future;
          return FakeBackend.json(
            201,
            messageJson(sequence: 4, mine: true, body: 'once'),
          );
        },
      );
      await tester.enterText(find.byKey(const Key('composer-field')), 'once');
      await tester.pump();
      await tester.tap(find.byKey(const Key('composer-send')));
      await tester.pump(const Duration(milliseconds: 30));
      expect(find.text('Sending…'), findsOneWidget);
      await tester.tap(find.text('Sending…'), warnIfMissed: false);
      await tester.pump(const Duration(milliseconds: 30));
      expect(h.backend.count('POST', _msgs()), 1);
      gate.complete();
      await tester.pumpAndSettle();
      expect(h.backend.count('POST', _msgs()), 1);
    });
  });

  group('account isolation (conversation route stays mounted)', () {
    testWidgets(
      'A\'s messages disappear at once, B loads from scratch and sees only B',
      (tester) async {
        var who = 'A';
        final gateB = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: '/chat/$conversationId',
          size: _phone,
          script: (b) {
            b.on(
              'GET',
              _convs,
              (_) => FakeBackend.json(200, pageJson(<Object?>[])),
            );
            b.on('GET', _unread, (_) => FakeBackend.json(200, {'count': 0}));
            b.on(
              'POST',
              _readPath(),
              (_) => FakeBackend.json(200, {'last_read_sequence': 1}),
            );
            b.on('GET', _msgs(), (_) async {
              if (who == 'B') await gateB.future;
              return FakeBackend.json(
                200,
                pageJson([messageJson(sequence: 1, body: 'PRIVATE OF $who')]),
              );
            });
          },
        );
        expect(find.text('PRIVATE OF A'), findsOneWidget);
        who = 'B';
        await switchAccountTo(tester, h, _b);
        expect(find.text('PRIVATE OF A'), findsNothing);
        expect(
          find.byType(CircularProgressIndicator),
          findsWidgets,
          reason: 'B is loading',
        );
        gateB.complete();
        await tester.pumpAndSettle();
        expect(find.text('PRIVATE OF B'), findsOneWidget);
        expect(find.text('PRIVATE OF A'), findsNothing);
      },
    );

    testWidgets(
      'A\'s draft never survives into B and B\'s send does not carry it',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/chat/$conversationId',
          size: _phone,
          script: (b) => _thread(
            b,
            send: (_) => FakeBackend.json(
              201,
              messageJson(sequence: 4, mine: true, body: 'x'),
            ),
          ),
        );
        await tester.enterText(
          find.byKey(const Key('composer-field')),
          'private message from A',
        );
        await tester.pump();
        await switchAccountTo(tester, h, _b);
        await tester.pumpAndSettle();
        expect(find.text('private message from A'), findsNothing);
        expect(
          tester
              .widget<TextField>(find.byKey(const Key('composer-field')))
              .controller!
              .text,
          isEmpty,
        );
        expect(
          tester
              .widget<FilledButton>(
                find.descendant(
                  of: find.byKey(const Key('composer-send')),
                  matching: find.byType(FilledButton),
                ),
              )
              .onPressed,
          isNull,
          reason: 'nothing to send for B',
        );
        expect(h.backend.count('POST', _msgs()), 0);
      },
    );

    for (final late in ['success', 'error']) {
      testWidgets(
        'a late $late of A\'s send is never shown to B and invalidates nothing',
        (tester) async {
          final gate = Completer<void>();
          final h = await pumpPatientApp(
            tester,
            path: '/chat/$conversationId',
            size: _phone,
            script: (b) => _thread(
              b,
              send: (_) async {
                await gate.future;
                return late == 'success'
                    ? FakeBackend.json(
                        201,
                        messageJson(
                          sequence: 4,
                          mine: true,
                          body: 'A SECRET SEND',
                        ),
                      )
                    : FakeBackend.error(500, 'server_error');
              },
            ),
          );
          await tester.enterText(
            find.byKey(const Key('composer-field')),
            'A SECRET SEND',
          );
          await tester.pump();
          await tester.tap(find.byKey(const Key('composer-send')));
          await tester.pump(const Duration(milliseconds: 30));
          await switchAccountTo(tester, h, _b);
          await tester.pumpAndSettle();
          final lists = h.backend.count('GET', _convs);
          final unreads = h.backend.count('GET', _unread);
          gate.complete();
          await tester.pumpAndSettle();
          expect(find.text('A SECRET SEND'), findsNothing);
          expect(find.byKey(const Key('composer-error')), findsNothing);
          expect(h.backend.count('GET', _convs), lists);
          expect(h.backend.count('GET', _unread), unreads);
          // B's composer is a fresh, usable one (A's pending state did not disable it)
          await tester.enterText(
            find.byKey(const Key('composer-field')),
            'hello from B',
          );
          await tester.pump();
          expect(
            tester
                .widget<FilledButton>(
                  find.descendant(
                    of: find.byKey(const Key('composer-send')),
                    matching: find.byType(FilledButton),
                  ),
                )
                .onPressed,
            isNotNull,
          );
        },
      );
    }

    testWidgets('A\'s conversation list disappears under B', (tester) async {
      var who = 'A';
      final gateB = Completer<void>();
      final h = await pumpPatientApp(
        tester,
        path: '/chat',
        size: _tall,
        script: (b) {
          b.on('GET', _unread, (_) => FakeBackend.json(200, {'count': 0}));
          b.on('GET', _convs, (_) async {
            if (who == 'B') await gateB.future;
            return FakeBackend.json(
              200,
              pageJson([conversationJson(name: 'PERSON FOR $who')]),
            );
          });
        },
      );
      expect(find.text('PERSON FOR A'), findsOneWidget);
      who = 'B';
      await switchAccountTo(tester, h, _b);
      expect(find.text('PERSON FOR A'), findsNothing);
      gateB.complete();
      await tester.pumpAndSettle();
      expect(find.text('PERSON FOR B'), findsOneWidget);
    });
  });

  group('starting from a reservation', () {
    testWidgets(
      'the patient detail offers one POST that opens the conversation',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/reservations/$reservationId',
          size: _tall,
          script: (b) {
            b.on(
              'GET',
              '/api/v1/reservations/me/$reservationId',
              (_) => FakeBackend.json(200, reservationJson()),
            );
            b.on(
              'POST',
              '/api/v1/chat/reservations/$reservationId/conversation',
              (_) => FakeBackend.json(201, conversationJson()),
            );
            _thread(b);
          },
        );
        await tester.ensureVisible(find.byKey(const Key('open-conversation')));
        await tester.tap(find.byKey(const Key('open-conversation')));
        await tester.pumpAndSettle();
        expect(
          h.backend.count(
            'POST',
            '/api/v1/chat/reservations/$reservationId/conversation',
          ),
          1,
        );
        expect(h.backend.count('GET', _msgs()), 1);
        expect(find.text('first mine'), findsOneWidget);
      },
    );

    testWidgets('the provider detail offers Message the patient', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/workspace/reservations/$reservationId',
        size: _tall,
        account: providerAccountJson(),
        script: (b) => b.on(
          'GET',
          '/api/v1/reservations/provider/$reservationId',
          (_) => FakeBackend.json(200, providerReservationJson()),
        ),
      );
      expect(find.text('Message the patient'), findsOneWidget);
    });

    testWidgets('a refusal is a fixed message', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/reservations/$reservationId',
        size: _tall,
        script: (b) {
          b.on(
            'GET',
            '/api/v1/reservations/me/$reservationId',
            (_) => FakeBackend.json(200, reservationJson()),
          );
          b.on(
            'POST',
            '/api/v1/chat/reservations/$reservationId/conversation',
            (_) => FakeBackend.error(
              404,
              'not_found',
              message: 'reservation 44 missing',
            ),
          );
        },
      );
      await tester.ensureVisible(find.byKey(const Key('open-conversation')));
      await tester.tap(find.byKey(const Key('open-conversation')));
      await tester.pumpAndSettle();
      expect(find.text("Couldn't open the conversation."), findsOneWidget);
      expect(find.textContaining('reservation 44'), findsNothing);
    });

    testWidgets('A\'s late open never navigates B', (tester) async {
      final gate = Completer<void>();
      final h = await pumpPatientApp(
        tester,
        path: '/reservations/$reservationId',
        size: _tall,
        script: (b) {
          b.on(
            'GET',
            '/api/v1/reservations/me/$reservationId',
            (_) => FakeBackend.json(200, reservationJson()),
          );
          b.on(
            'POST',
            '/api/v1/chat/reservations/$reservationId/conversation',
            (_) async {
              await gate.future;
              return FakeBackend.json(201, conversationJson());
            },
          );
          _thread(b);
        },
      );
      await tester.ensureVisible(find.byKey(const Key('open-conversation')));
      await tester.tap(find.byKey(const Key('open-conversation')));
      await tester.pump(const Duration(milliseconds: 30));
      await switchAccountTo(tester, h, _b);
      gate.complete();
      await tester.pumpAndSettle();
      expect(h.backend.count('GET', _msgs()), 0);
    });
  });

  testWidgets('Home shows the backend unread message count on Messages', (
    tester,
  ) async {
    await pumpPatientApp(
      tester,
      size: _tall,
      script: (b) =>
          b.on('GET', _unread, (_) => FakeBackend.json(200, {'count': 4})),
    );
    expect(find.byKey(const Key('explore-unread-messages')), findsOneWidget);
    expect(find.text('4'), findsOneWidget);
  });
}
