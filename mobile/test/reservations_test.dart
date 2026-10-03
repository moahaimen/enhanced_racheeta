import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/intl.dart' show DateFormat;
import 'package:racheeta_mobile/app/router.dart';
import 'package:racheeta_mobile/features/auth/application/providers.dart';

import 'support/fake_backend.dart';
import 'support/patient_support.dart';

const _list = '/api/v1/reservations/me';
const _detail = '/api/v1/reservations/me/$reservationId';
const _cancel = '/api/v1/reservations/me/$reservationId/cancel';
const _tall = Size(800, 1800);

String _local(int day, int hour) =>
    DateFormat.jm('en').format(DateTime(2026, 10, day, hour));

void main() {
  group('reservations list', () {
    testWidgets('groups upcoming and past/closed and shows backend facts', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/reservations',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _list,
          (_) => FakeBackend.json(
            200,
            pageJson([
              // backend order: newest appointment first
              reservationJson(
                id: 'r-future',
                status: 'CONFIRMED',
                startsAt: '2026-10-09T06:00:00Z',
                provider: 'Dr. Future',
              ),
              reservationJson(
                id: 'r-cancelled',
                status: 'CANCELLED',
                startsAt: '2026-10-08T06:00:00Z',
                provider: 'Dr. Cancelled',
              ),
              reservationJson(
                id: 'r-pending',
                status: 'PENDING',
                startsAt: '2026-10-05T06:00:00Z',
                provider: 'Dr. Pending',
              ),
              reservationJson(
                id: 'r-done',
                status: 'COMPLETED',
                startsAt: '2026-09-20T06:00:00Z',
                provider: 'Dr. Done',
              ),
            ]),
          ),
        ),
      );
      expect(find.text('My appointments'), findsWidgets);
      expect(find.text('Upcoming'), findsOneWidget);
      expect(find.text('Past and closed'), findsOneWidget);
      // upcoming first: live status AND a start in the future
      double y(String name) => tester.getTopLeft(find.text(name)).dy;
      expect(y('Upcoming'), lessThan(y('Dr. Future')));
      expect(y('Dr. Future'), lessThan(y('Dr. Pending')));
      expect(y('Dr. Pending'), lessThan(y('Past and closed')));
      expect(y('Past and closed'), lessThan(y('Dr. Cancelled')));
      expect(y('Dr. Cancelled'), lessThan(y('Dr. Done')));
      expect(find.text('Confirmed'), findsOneWidget);
      expect(find.text('Cancelled'), findsOneWidget);
      expect(find.text('Completed'), findsOneWidget);
      expect(find.text('Pending'), findsOneWidget);
      expect(h.backend.to('GET', _list).single.query['page_size'], 20);
    });

    testWidgets('start times are shown in the (injected) local time', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/reservations',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _list,
          (_) => FakeBackend.json(
            200,
            pageJson([reservationJson(startsAt: '2026-10-05T06:00:00Z')]),
          ),
        ),
      );
      // 06:00Z is 09:00 for the UTC+3 reader; the raw UTC clock value is never printed.
      expect(find.textContaining(_local(5, 9)), findsOneWidget);
      expect(find.textContaining(_local(5, 6)), findsNothing);
    });

    testWidgets('empty list explains itself and offers to find a provider', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/reservations',
        size: _tall,
        script: (b) => b
          ..on(
            'GET',
            _list,
            (_) => FakeBackend.json(200, pageJson(<Object?>[])),
          )
          ..on(
            'GET',
            '/api/v1/providers',
            (_) => FakeBackend.json(200, pageJson(<Object?>[])),
          ),
      );
      expect(find.text('No appointments yet'), findsOneWidget);
      await tester.tap(find.text('Find a provider'));
      await tester.pumpAndSettle();
      expect(
        h.container.read(routerProvider).state.matchedLocation,
        '/providers',
      );
    });

    testWidgets('failure shows a safe message; Try again recovers', (
      tester,
    ) async {
      var fail = true;
      await pumpPatientApp(
        tester,
        path: '/reservations',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _list,
          (_) => fail
              ? FakeBackend.error(
                  500,
                  'server_error',
                  message: 'Traceback: secret',
                )
              : FakeBackend.json(200, pageJson([reservationJson()])),
        ),
      );
      expect(
        find.textContaining('Something went wrong on our side'),
        findsOneWidget,
      );
      expect(find.textContaining('secret'), findsNothing);
      fail = false;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Dr. Sara Ahmed'), findsOneWidget);
    });

    testWidgets('pagination appends the next page', (tester) async {
      final h = await pumpPatientApp(
        tester,
        path: '/reservations',
        size: _tall,
        script: (b) => b.on('GET', _list, (r) {
          if (r.query['page'] == 2) {
            return FakeBackend.json(
              200,
              pageJson([
                reservationJson(id: 'r2', provider: 'Dr. Second'),
              ], count: 2),
            );
          }
          return FakeBackend.json(
            200,
            pageJson(
              [reservationJson(provider: 'Dr. First')],
              count: 2,
              next: 'https://api.test/api/v1/reservations/me?page=2',
            ),
          );
        }),
      );
      expect(find.text('Dr. Second'), findsNothing);
      await tester.tap(find.text('Load more'));
      await tester.pumpAndSettle();
      expect(find.text('Dr. First'), findsOneWidget);
      expect(find.text('Dr. Second'), findsOneWidget);
      expect(find.text('Load more'), findsNothing);
      expect(h.backend.to('GET', _list).map((r) => r.query['page']), [null, 2]);
    });

    testWidgets('a reservation with an unknown future status still renders', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/reservations',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _list,
          (_) => FakeBackend.json(
            200,
            pageJson([
              reservationJson(status: 'ARCHIVED', provider: 'Dr. Odd'),
            ]),
          ),
        ),
      );
      expect(find.text('Dr. Odd'), findsOneWidget);
      expect(find.text('Unknown'), findsOneWidget);
    });

    testWidgets(
      'account switching: another account never sees this list, late answers are dropped',
      (tester) async {
        final slow = Completer<void>();
        var account = 'A';
        final h = await pumpPatientApp(
          tester,
          script: (b) => b
            ..on('GET', _list, (_) async {
              if (account == 'A') {
                await slow.future;
                return FakeBackend.json(
                  200,
                  pageJson([reservationJson(provider: 'ACCOUNT A DOCTOR')]),
                );
              }
              return FakeBackend.json(
                200,
                pageJson([
                  reservationJson(id: 'rb', provider: 'ACCOUNT B DOCTOR'),
                ]),
              );
            })
            ..on('POST', '/api/v1/auth/logout', (_) => FakeBackend.noContent())
            ..on(
              'POST',
              '/api/v1/auth/login',
              (_) => FakeBackend.json(200, tokens('ab', 'rb')),
            ),
        );
        h.container.read(routerProvider).go('/reservations');
        await tester.pump(const Duration(milliseconds: 50));
        // Real async work (dio) must run outside FakeAsync, or the awaited call never completes.
        await tester.runAsync(
          () => h.container.read(sessionControllerProvider.notifier).logout(),
        );
        account = 'B';
        h.backend.on(
          'GET',
          '/api/v1/me',
          (_) => FakeBackend.json(
            200,
            accountJson(
              id: '99999999-9999-4999-8999-999999999999',
              name: 'Account B',
            ),
          ),
        );
        await tester.runAsync(
          () => h.container
              .read(sessionControllerProvider.notifier)
              .login(email: 'b@example.com', password: 'pw'),
        );
        slow.complete();
        await tester.pump(const Duration(milliseconds: 100));
        h.container.read(routerProvider).go('/reservations');
        await tester.pump(const Duration(milliseconds: 100));
        await tester.pump(const Duration(milliseconds: 100));
        expect(find.text('ACCOUNT A DOCTOR'), findsNothing);
        expect(find.text('ACCOUNT B DOCTOR'), findsOneWidget);
      },
    );
  });

  group('reservation detail', () {
    void detailScript(FakeBackend b, Map<String, Object?> json) =>
        b.on('GET', _detail, (_) => FakeBackend.json(200, json));

    testWidgets('shows the snapshot, local time and the status history', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/reservations/$reservationId',
        size: _tall,
        script: (b) => detailScript(
          b,
          reservationJson(
            status: 'CONFIRMED',
            note: 'bring my results',
            transitions: [
              {
                'from_status': '',
                'to_status': 'PENDING',
                'reason': '',
                'created_at': '2026-10-03T08:00:00Z',
              },
              {
                'from_status': 'PENDING',
                'to_status': 'CONFIRMED',
                'reason': '',
                'created_at': '2026-10-03T08:30:00Z',
              },
            ],
          ),
        ),
      );
      expect(find.text('Dr. Sara Ahmed'), findsOneWidget);
      expect(find.text('Consultation'), findsOneWidget);
      expect(find.text('bring my results'), findsOneWidget);
      expect(find.text('Status history'), findsOneWidget);
      expect(find.textContaining(_local(5, 9)), findsWidgets);
      expect(find.textContaining('25,000'), findsOneWidget);
      expect(find.text('Confirmed'), findsWidgets);
    });

    testWidgets(
      'a reservation whose provider was deleted still renders from its snapshots',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/reservations/$reservationId',
          size: _tall,
          script: (b) => b.on(
            'GET',
            _detail,
            (_) => FakeBackend.json(200, {
              ...reservationJson(),
              'provider_id': null,
            }),
          ),
        );
        expect(find.text('Dr. Sara Ahmed'), findsOneWidget);
        expect(find.text('View provider'), findsNothing);
      },
    );

    testWidgets(
      'a missing or foreign reservation is the generic not-found text',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/reservations/$reservationId',
          size: _tall,
          script: (b) =>
              b.on('GET', _detail, (_) => FakeBackend.error(404, 'not_found')),
        );
        expect(find.text("We couldn't find that."), findsOneWidget);
      },
    );

    // One app per case (several apps in one test would leave timers behind).
    for (final c in const [
      ('PENDING', '2026-10-05T06:00:00Z', true),
      ('CONFIRMED', '2026-10-05T06:00:00Z', true),
      ('PENDING', '2026-10-02T06:00:00Z', false), // already started
      ('CANCELLED', '2026-10-05T06:00:00Z', false),
      ('COMPLETED', '2026-10-05T06:00:00Z', false),
      ('REJECTED', '2026-10-05T06:00:00Z', false),
      ('NO_SHOW', '2026-10-05T06:00:00Z', false),
    ]) {
      testWidgets(
        'Cancel is ${c.$3 ? '' : 'not '}offered for ${c.$1} starting ${c.$2}',
        (tester) async {
          await pumpPatientApp(
            tester,
            path: '/reservations/$reservationId',
            size: _tall,
            script: (b) =>
                detailScript(b, reservationJson(status: c.$1, startsAt: c.$2)),
          );
          expect(
            find.widgetWithText(FilledButton, 'Cancel appointment'),
            c.$3 ? findsOneWidget : findsNothing,
          );
        },
      );
    }

    Future<Harness> openCancellable(WidgetTester tester, {Responder? cancel}) =>
        pumpPatientApp(
          tester,
          path: '/reservations/$reservationId',
          size: _tall,
          script: (b) {
            detailScript(b, reservationJson());
            if (cancel != null) b.on('POST', _cancel, cancel);
          },
        );

    Finder cancelButton() =>
        find.widgetWithText(FilledButton, 'Cancel appointment');

    testWidgets('declining the confirmation sends nothing', (tester) async {
      final h = await openCancellable(
        tester,
        cancel: (_) =>
            FakeBackend.json(200, reservationJson(status: 'CANCELLED')),
      );
      await tester.tap(cancelButton());
      await tester.pumpAndSettle();
      expect(find.text('Cancel this appointment?'), findsOneWidget);
      await tester.tap(find.text('Keep appointment'));
      await tester.pumpAndSettle();
      expect(h.backend.count('POST', _cancel), 0);
      expect(find.byKey(const Key('reservation-message')), findsNothing);
    });

    testWidgets(
      'confirming sends one POST with an empty body and refreshes the record',
      (tester) async {
        var cancelled = false;
        final h = await pumpPatientApp(
          tester,
          path: '/reservations/$reservationId',
          size: _tall,
          script: (b) => b
            ..on(
              'GET',
              _detail,
              (_) => FakeBackend.json(
                200,
                reservationJson(status: cancelled ? 'CANCELLED' : 'PENDING'),
              ),
            )
            ..on('POST', _cancel, (_) {
              cancelled = true;
              return FakeBackend.json(
                200,
                reservationJson(status: 'CANCELLED'),
              );
            }),
        );
        await tester.tap(cancelButton());
        await tester.pumpAndSettle();
        await tester.tap(
          find.descendant(
            of: find.byType(AlertDialog),
            matching: find.text('Cancel appointment'),
          ),
        );
        await tester.pumpAndSettle();

        expect(h.backend.to('POST', _cancel), hasLength(1));
        expect(h.backend.to('POST', _cancel).single.body, isEmpty);
        expect(find.text('The appointment was cancelled.'), findsOneWidget);
        expect(
          h.backend.count('GET', _detail),
          2,
          reason: 'refetched from the backend',
        );
        expect(find.text('Cancelled'), findsWidgets);
        expect(cancelButton(), findsNothing);
      },
    );

    testWidgets(
      'a duplicate tap while cancelling sends ONE request and shows progress',
      (tester) async {
        final gate = Completer<void>();
        final h = await openCancellable(
          tester,
          cancel: (_) async {
            await gate.future;
            return FakeBackend.json(200, reservationJson(status: 'CANCELLED'));
          },
        );
        await tester.tap(cancelButton());
        await tester.pumpAndSettle();
        await tester.tap(
          find.descendant(
            of: find.byType(AlertDialog),
            matching: find.text('Cancel appointment'),
          ),
        );
        await tester.pump();
        expect(find.text('Cancelling…'), findsOneWidget);
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        await tester.tap(find.text('Cancelling…'), warnIfMissed: false);
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 20));
        expect(h.backend.count('POST', _cancel), 1);
        gate.complete();
        await tester.pumpAndSettle();
        expect(h.backend.count('POST', _cancel), 1);
      },
    );

    testWidgets(
      'invalid_transition (400): localized message and the true state is refetched',
      (tester) async {
        final h = await openCancellable(
          tester,
          cancel: (_) => FakeBackend.error(
            400,
            'invalid_transition',
            message: 'Cannot cancel',
          ),
        );
        await tester.tap(cancelButton());
        await tester.pumpAndSettle();
        await tester.tap(
          find.descendant(
            of: find.byType(AlertDialog),
            matching: find.text('Cancel appointment'),
          ),
        );
        await tester.pumpAndSettle();
        expect(
          find.text('This appointment can no longer be cancelled.'),
          findsOneWidget,
        );
        expect(find.textContaining('Cannot cancel'), findsNothing);
        expect(h.backend.count('POST', _cancel), 1);
        expect(h.backend.count('GET', _detail), 2);
      },
    );

    testWidgets('a network failure is not retried automatically', (
      tester,
    ) async {
      final h = await openCancellable(tester, cancel: FakeBackend.networkDown);
      await tester.tap(cancelButton());
      await tester.pumpAndSettle();
      await tester.tap(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.text('Cancel appointment'),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('Could not reach the server'), findsOneWidget);
      await tester.pump(const Duration(seconds: 30));
      expect(h.backend.count('POST', _cancel), 1);
    });
  });

  group('patient screens: Arabic', () {
    testWidgets('list and detail render right-to-left Arabic copy', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/reservations',
        size: _tall,
        language: 'ar',
        script: (b) => b
          ..on(
            'GET',
            _list,
            (_) => FakeBackend.json(200, pageJson([reservationJson()])),
          )
          ..on('GET', _detail, (_) => FakeBackend.json(200, reservationJson())),
      );
      expect(find.text('مواعيدي'), findsWidgets);
      expect(find.text('القادمة'), findsOneWidget);
      expect(find.text('قيد الانتظار'), findsOneWidget);
      expect(
        Directionality.of(tester.element(find.text('القادمة'))),
        TextDirection.rtl,
      );
      h.container.read(routerProvider).go('/reservations/$reservationId');
      await tester.pumpAndSettle();
      expect(find.text('سجل الحالة'), findsOneWidget);
      expect(find.text('إلغاء الموعد'), findsOneWidget);
    });
  });
}
