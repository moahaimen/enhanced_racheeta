import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/features/push/push_registration.dart';
import 'package:racheeta_mobile/features/push/push_source.dart';

import 'support/comms_support.dart';
import 'support/domain_support.dart' show recruiterAccountJson;
import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart'
    show providerAccountJson, switchAccountTo;

const _list = '/api/v1/notifications/';
const _unread = '/api/v1/notifications/unread-count/';
const _readAll = '/api/v1/notifications/read-all/';
String _read(String id) => '/api/v1/notifications/$id/read/';
const _tall = Size(800, 2400);
const _phone = Size(360, 780);

final Map<String, Object?> _b = accountJson(
  id: '99999999-9999-4999-8999-999999999999',
  name: 'Patient B',
);

void _basic(FakeBackend b, {List<Object?>? items, int unread = 2}) => b
  ..on(
    'GET',
    _list,
    (_) => FakeBackend.json(
      200,
      pageJson(
        items ??
            [
              notificationJson(),
              notificationJson(
                id: 'aaaa1111-0000-4000-8000-000000000002',
                isRead: true,
                title: 'Reservation created',
              ),
            ],
      ),
    ),
  )
  ..on('GET', _unread, (_) => FakeBackend.json(200, {'count': unread}));

void main() {
  group('list', () {
    testWidgets('shows backend order, unread/read state and a localized time', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        script: _basic,
      );
      expect(find.text('Reservation confirmed'), findsOneWidget);
      expect(find.text('Reservation created'), findsOneWidget);
      expect(find.byKey(const Key('unread-$notificationId')), findsOneWidget);
      expect(
        find.byKey(const Key('read-aaaa1111-0000-4000-8000-000000000002')),
        findsOneWidget,
      );
      expect(find.text('2 unread'), findsOneWidget);
      // 08:00 UTC is 11:00 on the UTC+3 test wall clock
      expect(find.textContaining('11:00'), findsWidgets);
      expect(find.byType(Semantics), findsWidgets);
    });

    testWidgets('an unknown future type or empty title never breaks the list', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        script: (b) => _basic(
          b,
          items: [
            notificationJson(
              event: 'JOB_APPLICATION_UPDATED',
              category: 'JOBS',
              resourceType: 'JOB',
              title: '',
              body: '',
            ),
            notificationJson(
              id: 'aaaa1111-0000-4000-8000-000000000009',
              title: 'Still shown',
            ),
          ],
        ),
      );
      expect(find.text('Notification'), findsOneWidget);
      expect(find.text('Still shown'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('pagination keeps rows when a later page fails', (
      tester,
    ) async {
      var fail = true;
      await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        script: (b) {
          b.on('GET', _unread, (_) => FakeBackend.json(200, {'count': 1}));
          b.on('GET', _list, (r) {
            if (r.query['page'] == 2) {
              return fail
                  ? FakeBackend.error(500, 'server_error')
                  : FakeBackend.json(
                      200,
                      pageJson([
                        notificationJson(
                          id: 'aaaa1111-0000-4000-8000-000000000002',
                          title: 'Second page',
                        ),
                      ], count: 2),
                    );
            }
            return FakeBackend.json(
              200,
              pageJson(
                [notificationJson(title: 'First page')],
                count: 2,
                next: 'https://api.test/x?page=2',
              ),
            );
          });
        },
      );
      await tester.tap(find.text('Load more'));
      await tester.pumpAndSettle();
      expect(find.text('Could not load more results.'), findsOneWidget);
      expect(find.text('First page'), findsOneWidget);
      fail = false;
      await tester.tap(find.text('Load more'));
      await tester.pumpAndSettle();
      expect(find.text('Second page'), findsOneWidget);
    });

    testWidgets('empty state', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        script: (b) => _basic(b, items: const [], unread: 0),
      );
      expect(find.text('No notifications yet'), findsOneWidget);
    });

    testWidgets('a failure is safe and retry recovers', (tester) async {
      var fail = true;
      await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        script: (b) {
          b.on('GET', _unread, (_) => FakeBackend.json(200, {'count': 0}));
          b.on(
            'GET',
            _list,
            (_) => fail
                ? FakeBackend.error(
                    500,
                    'server_error',
                    message: 'Traceback secret',
                  )
                : FakeBackend.json(200, pageJson([notificationJson()])),
          );
        },
      );
      expect(find.textContaining('Traceback'), findsNothing);
      fail = false;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Reservation confirmed'), findsOneWidget);
    });

    testWidgets('Arabic right-to-left at phone width', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _phone,
        language: 'ar',
        script: _basic,
      );
      expect(find.text('الإشعارات'), findsWidgets);
      expect(find.text('تحديد الكل كمقروء'), findsOneWidget);
      expect(
        Directionality.of(tester.element(find.text('تحديد الكل كمقروء'))),
        TextDirection.rtl,
      );
      expect(tester.takeException(), isNull);
    });
  });

  group('mark read', () {
    testWidgets(
      'opening an unread row sends exactly one POST, then reloads list and count from the backend',
      (tester) async {
        var read = false;
        final h = await pumpPatientApp(
          tester,
          path: '/notifications',
          size: _tall,
          script: (b) {
            b.on(
              'GET',
              _list,
              (_) => FakeBackend.json(
                200,
                pageJson([
                  notificationJson(
                    isRead: read,
                    event: 'JOB_APPLICATION_UPDATED',
                  ),
                ]),
              ),
            );
            b.on(
              'GET',
              _unread,
              (_) => FakeBackend.json(200, {'count': read ? 0 : 1}),
            );
            b.on('POST', _read(notificationId), (_) {
              read = true;
              return FakeBackend.json(
                200,
                notificationJson(
                  isRead: true,
                  event: 'JOB_APPLICATION_UPDATED',
                ),
              );
            });
          },
        );
        expect(find.text('1 unread'), findsOneWidget);
        await tester.tap(find.byKey(const Key('notification-$notificationId')));
        await tester.pumpAndSettle();
        final posts = h.backend.to('POST', _read(notificationId));
        expect(posts, hasLength(1));
        expect(posts.single.body, isEmpty);
        expect(find.byKey(const Key('read-$notificationId')), findsOneWidget);
        expect(find.text('0 unread'), findsOneWidget);
        // an already-read row sends nothing
        await tester.tap(find.byKey(const Key('notification-$notificationId')));
        await tester.pumpAndSettle();
        expect(h.backend.count('POST', _read(notificationId)), 1);
      },
    );

    testWidgets('a failed mark shows a fixed message and is never retried', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        script: (b) {
          _basic(b, items: [notificationJson(event: 'FUTURE_EVENT')]);
          b.on(
            'POST',
            _read(notificationId),
            (_) => FakeBackend.error(500, 'server_error', message: 'raw boom'),
          );
        },
      );
      await tester.tap(find.byKey(const Key('notification-$notificationId')));
      await tester.pumpAndSettle();
      expect(
        find.text("Couldn't update the notification. Try again."),
        findsOneWidget,
      );
      expect(find.textContaining('raw boom'), findsNothing);
      await tester.pump(const Duration(seconds: 30));
      expect(h.backend.count('POST', _read(notificationId)), 1);
    });

    testWidgets('a duplicate tap while pending sends one request', (
      tester,
    ) async {
      final gate = Completer<void>();
      final h = await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        script: (b) {
          _basic(b, items: [notificationJson(event: 'FUTURE_EVENT')]);
          b.on('POST', _read(notificationId), (_) async {
            await gate.future;
            return FakeBackend.json(
              200,
              notificationJson(isRead: true, event: 'FUTURE_EVENT'),
            );
          });
        },
      );
      await tester.tap(find.byKey(const Key('notification-$notificationId')));
      await tester.pump(const Duration(milliseconds: 30));
      await tester.tap(find.byKey(const Key('notification-$notificationId')));
      await tester.pump(const Duration(milliseconds: 30));
      expect(h.backend.count('POST', _read(notificationId)), 1);
      gate.complete();
      await tester.pumpAndSettle();
      expect(h.backend.count('POST', _read(notificationId)), 1);
    });

    testWidgets('mark all read is one explicit request and reloads', (
      tester,
    ) async {
      var done = false;
      final h = await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        script: (b) {
          b.on(
            'GET',
            _list,
            (_) => FakeBackend.json(
              200,
              pageJson([
                notificationJson(isRead: done),
                notificationJson(
                  id: 'aaaa1111-0000-4000-8000-000000000002',
                  isRead: done,
                ),
              ]),
            ),
          );
          b.on(
            'GET',
            _unread,
            (_) => FakeBackend.json(200, {'count': done ? 0 : 2}),
          );
          b.on('POST', _readAll, (_) {
            done = true;
            return FakeBackend.json(200, {'updated': 2});
          });
        },
      );
      await tester.tap(find.byKey(const Key('notifications-mark-all')));
      await tester.pumpAndSettle();
      final posts = h.backend.to('POST', _readAll);
      expect(posts, hasLength(1));
      expect(posts.single.body, isEmpty);
      expect(find.text('2 notifications marked as read.'), findsOneWidget);
      expect(find.text('0 unread'), findsOneWidget);
      expect(
        tester
            .widget<TextButton>(find.byKey(const Key('notifications-mark-all')))
            .onPressed,
        isNull,
        reason: 'nothing left to mark',
      );
    });

    testWidgets('a failed mark-all is a fixed message and not retried', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        script: (b) {
          _basic(b);
          b.on('POST', _readAll, FakeBackend.networkDown);
        },
      );
      await tester.tap(find.byKey(const Key('notifications-mark-all')));
      await tester.pumpAndSettle();
      expect(
        find.text("Couldn't update the notification. Try again."),
        findsOneWidget,
      );
      await tester.pump(const Duration(seconds: 30));
      expect(h.backend.count('POST', _readAll), 1);
    });
  });

  group('opening a notification', () {
    testWidgets('a patient is taken to the reservation, validated and gated', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        script: (b) {
          _basic(b, items: [notificationJson(isRead: true)]);
          b.on(
            'GET',
            '/api/v1/reservations/me/$reservationId',
            (_) => FakeBackend.json(200, reservationJson()),
          );
        },
      );
      await tester.tap(find.byKey(const Key('notification-$notificationId')));
      await tester.pumpAndSettle();
      expect(
        h.backend.count('GET', '/api/v1/reservations/me/$reservationId'),
        1,
      );
    });

    testWidgets('a provider account is taken to the provider-side detail', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        account: providerAccountJson(),
        script: (b) {
          _basic(b, items: [notificationJson(isRead: true)]);
          b.on(
            'GET',
            '/api/v1/reservations/provider/$reservationId',
            (_) => FakeBackend.error(404, 'not_found'),
          );
        },
      );
      await tester.tap(find.byKey(const Key('notification-$notificationId')));
      await tester.pumpAndSettle();
      expect(
        h.backend.count('GET', '/api/v1/reservations/provider/$reservationId'),
        1,
      );
      expect(
        h.backend.count('GET', '/api/v1/reservations/me/$reservationId'),
        0,
      );
    });

    testWidgets(
      'unknown event, unknown resource, malformed id and a capability-less account do not navigate',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/notifications',
          size: _tall,
          account: recruiterAccountJson(),
          script: (b) => _basic(
            b,
            items: [
              notificationJson(isRead: true, event: 'FUTURE_EVENT'),
              notificationJson(
                id: 'aaaa1111-0000-4000-8000-000000000002',
                isRead: true,
                resourceType: 'JOB',
              ),
              notificationJson(
                id: 'aaaa1111-0000-4000-8000-000000000003',
                isRead: true,
                resourceId: '../../admin',
              ),
              notificationJson(
                id: 'aaaa1111-0000-4000-8000-000000000004',
                isRead: true,
              ),
            ],
          ),
        );
        for (final id in [
          notificationId,
          'aaaa1111-0000-4000-8000-000000000002',
          'aaaa1111-0000-4000-8000-000000000003',
          'aaaa1111-0000-4000-8000-000000000004',
        ]) {
          await tester.tap(find.byKey(Key('notification-$id')));
          await tester.pumpAndSettle();
        }
        expect(find.text('Notifications'), findsWidgets);
        expect(
          h.backend.requests.where((r) => r.path.contains('/reservations/')),
          isEmpty,
        );
      },
    );
  });

  group('account isolation (route stays mounted)', () {
    testWidgets('A\'s notifications disappear at once; B sees only B', (
      tester,
    ) async {
      var who = 'A';
      final gateB = Completer<void>();
      final h = await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        script: (b) {
          b.on('GET', _unread, (_) => FakeBackend.json(200, {'count': 1}));
          b.on('GET', _list, (_) async {
            if (who == 'B') await gateB.future;
            return FakeBackend.json(
              200,
              pageJson([notificationJson(title: 'NOTE OF $who')]),
            );
          });
        },
      );
      expect(find.text('NOTE OF A'), findsOneWidget);
      who = 'B';
      await switchAccountTo(tester, h, _b);
      expect(find.text('NOTE OF A'), findsNothing);
      expect(
        find.text('1 unread'),
        findsNothing,
        reason: 'B\'s count not loaded yet',
      );
      gateB.complete();
      await tester.pumpAndSettle();
      expect(find.text('NOTE OF B'), findsOneWidget);
      expect(find.text('NOTE OF A'), findsNothing);
    });

    for (final late in ['success', 'error']) {
      testWidgets(
        'a late $late of A\'s mark-read is never shown to B and reloads nothing',
        (tester) async {
          final gate = Completer<void>();
          final h = await pumpPatientApp(
            tester,
            path: '/notifications',
            size: _tall,
            script: (b) {
              _basic(b, items: [notificationJson(event: 'FUTURE_EVENT')]);
              b.on('POST', _read(notificationId), (_) async {
                await gate.future;
                return late == 'success'
                    ? FakeBackend.json(
                        200,
                        notificationJson(isRead: true, event: 'FUTURE_EVENT'),
                      )
                    : FakeBackend.error(500, 'server_error');
              });
            },
          );
          await tester.tap(
            find.byKey(const Key('notification-$notificationId')),
          );
          await tester.pump(const Duration(milliseconds: 30));
          await switchAccountTo(tester, h, _b);
          await tester.pumpAndSettle();
          final lists = h.backend.count('GET', _list);
          final unreads = h.backend.count('GET', _unread);
          gate.complete();
          await tester.pumpAndSettle();
          expect(
            find.text("Couldn't update the notification. Try again."),
            findsNothing,
          );
          expect(h.backend.count('GET', _list), lists);
          expect(h.backend.count('GET', _unread), unreads);
          // B can mark normally: the old pending state did not leak
          expect(
            find.byKey(const Key('notifications-mark-all')),
            findsOneWidget,
          );
        },
      );
    }

    testWidgets('A\'s unread badge on Home never shows under B', (
      tester,
    ) async {
      var who = 'A';
      final gateB = Completer<void>();
      final h = await pumpPatientApp(
        tester,
        size: _tall,
        script: (b) {
          b.on('GET', _unread, (_) async {
            if (who == 'B') await gateB.future;
            return FakeBackend.json(200, {'count': who == 'A' ? 7 : 3});
          });
        },
      );
      expect(
        find.byKey(const Key('explore-unread-notifications')),
        findsOneWidget,
      );
      expect(find.text('7'), findsOneWidget);
      who = 'B';
      await switchAccountTo(tester, h, _b);
      expect(find.text('7'), findsNothing);
      gateB.complete();
      await tester.pumpAndSettle();
      expect(find.text('3'), findsOneWidget);
    });
  });

  group('push permission prompt', () {
    testWidgets(
      'shown once when undetermined; allowing asks the OS exactly once',
      (tester) async {
        final source = FakePushSource(
          currentPermission: PushPermission.notDetermined,
        );
        await pumpPatientApp(
          tester,
          path: '/notifications',
          size: _tall,
          overrides: [pushSourceProvider.overrideWithValue(source)],
          script: (b) {
            _basic(b);
            b.on(
              'POST',
              '/api/v1/notifications/push-devices/',
              (_) => FakeBackend.json(200, {
                'id': 'f1',
                'platform': 'ANDROID',
                'is_active': true,
                'last_registered_at': '2026-10-03T08:00:00Z',
              }),
            );
          },
        );
        expect(find.byKey(const Key('push-prompt')), findsOneWidget);
        await tester.tap(find.byKey(const Key('push-allow')));
        await tester.pumpAndSettle();
        expect(source.permissionRequests, 1);
        expect(find.byKey(const Key('push-prompt')), findsNothing);
      },
    );

    testWidgets('denied push never hides persistent notifications', (
      tester,
    ) async {
      final source = FakePushSource(currentPermission: PushPermission.denied);
      await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        overrides: [pushSourceProvider.overrideWithValue(source)],
        script: _basic,
      );
      expect(find.byKey(const Key('push-denied')), findsOneWidget);
      expect(find.text('Reservation confirmed'), findsOneWidget);
      expect(find.byKey(const Key('push-prompt')), findsNothing);
    });
  });
}
