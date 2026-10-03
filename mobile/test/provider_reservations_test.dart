import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/intl.dart' show DateFormat;
import 'package:racheeta_mobile/app/router.dart';

import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart';

const _list = '/api/v1/reservations/provider';
const _detail = '/api/v1/reservations/provider/$reservationId';
const _transition = '/api/v1/reservations/provider/$reservationId/transition';
const _tall = Size(800, 2400);

String _local(int day, int hour) =>
    DateFormat.jm('en').format(DateTime(2026, 10, day, hour));

// "Now" is 2026-10-03T09:00Z.
const _future = '2026-10-05T06:00:00Z'; // Oct 5, 09:00 local
const _past = '2026-10-02T06:00:00Z';

void main() {
  group('provider reservations list', () {
    testWidgets(
      'shows the backend order with patient, service, local time and status',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/workspace/reservations',
          size: _tall,
          account: providerAccountJson(),
          script: (b) => b.on(
            'GET',
            _list,
            (_) => FakeBackend.json(
              200,
              pageJson([
                providerReservationJson(
                  id: 'r1',
                  patient: 'Newest Patient',
                  startsAt: '2026-10-09T06:00:00Z',
                ),
                providerReservationJson(
                  id: 'r2',
                  patient: 'Middle Patient',
                  status: 'CONFIRMED',
                  startsAt: _future,
                ),
                providerReservationJson(
                  id: 'r3',
                  patient: 'Oldest Patient',
                  status: 'COMPLETED',
                  startsAt: _past,
                ),
              ]),
            ),
          ),
        );
        double y(String text) => tester.getTopLeft(find.text(text)).dy;
        expect(y('Newest Patient'), lessThan(y('Middle Patient')));
        expect(y('Middle Patient'), lessThan(y('Oldest Patient')));
        expect(find.text('Pending'), findsOneWidget);
        expect(find.text('Confirmed'), findsOneWidget);
        expect(find.text('Completed'), findsOneWidget);
        // 06:00Z is 09:00 for the UTC+3 reader
        expect(
          find.text(
            DateFormat.yMMMEd('en').add_jm().format(DateTime(2026, 10, 5, 9)),
          ),
          findsOneWidget,
        );
        expect(find.textContaining(_local(5, 6)), findsNothing);
        expect(h.backend.to('GET', _list).single.query['page_size'], 20);
      },
    );

    testWidgets('pagination appends the next page', (tester) async {
      final h = await pumpPatientApp(
        tester,
        path: '/workspace/reservations',
        size: _tall,
        account: providerAccountJson(),
        script: (b) => b.on('GET', _list, (r) {
          if (r.query['page'] == 2) {
            return FakeBackend.json(
              200,
              pageJson([
                providerReservationJson(id: 'r2', patient: 'Second Patient'),
              ], count: 2),
            );
          }
          return FakeBackend.json(
            200,
            pageJson(
              [providerReservationJson(patient: 'First Patient')],
              count: 2,
              next: 'https://api.test/x?page=2',
            ),
          );
        }),
      );
      expect(find.text('Second Patient'), findsNothing);
      await tester.tap(find.text('Load more'));
      await tester.pumpAndSettle();
      expect(find.text('First Patient'), findsOneWidget);
      expect(find.text('Second Patient'), findsOneWidget);
      expect(find.text('Load more'), findsNothing);
      expect(h.backend.to('GET', _list).map((r) => r.query['page']), [null, 2]);
    });

    testWidgets(
      'a failing next page keeps the loaded items and can be retried',
      (tester) async {
        var fail = true;
        await pumpPatientApp(
          tester,
          path: '/workspace/reservations',
          size: _tall,
          account: providerAccountJson(),
          script: (b) => b.on('GET', _list, (r) {
            if (r.query['page'] == 2) {
              return fail
                  ? FakeBackend.error(500, 'server_error')
                  : FakeBackend.json(
                      200,
                      pageJson([
                        providerReservationJson(
                          id: 'r2',
                          patient: 'Second Patient',
                        ),
                      ], count: 2),
                    );
            }
            return FakeBackend.json(
              200,
              pageJson(
                [providerReservationJson(patient: 'First Patient')],
                count: 2,
                next: 'https://api.test/x?page=2',
              ),
            );
          }),
        );
        await tester.tap(find.text('Load more'));
        await tester.pumpAndSettle();
        expect(find.text('Could not load more results.'), findsOneWidget);
        expect(find.text('First Patient'), findsOneWidget);
        fail = false;
        await tester.tap(find.text('Load more'));
        await tester.pumpAndSettle();
        expect(find.text('Second Patient'), findsOneWidget);
      },
    );

    testWidgets('empty list explains itself', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/workspace/reservations',
        size: _tall,
        account: providerAccountJson(),
        script: (b) => b.on(
          'GET',
          _list,
          (_) => FakeBackend.json(200, pageJson(<Object?>[])),
        ),
      );
      expect(find.text('No bookings yet'), findsOneWidget);
    });

    testWidgets('a failure shows a safe message and Try again recovers', (
      tester,
    ) async {
      var fail = true;
      await pumpPatientApp(
        tester,
        path: '/workspace/reservations',
        size: _tall,
        account: providerAccountJson(),
        script: (b) => b.on(
          'GET',
          _list,
          (_) => fail
              ? FakeBackend.error(
                  500,
                  'server_error',
                  message: 'Traceback: secret',
                )
              : FakeBackend.json(200, pageJson([providerReservationJson()])),
        ),
      );
      expect(find.textContaining('secret'), findsNothing);
      fail = false;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Layla Hassan'), findsOneWidget);
    });

    testWidgets('a 403 (no provider profile) gets the guidance text', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/workspace/reservations',
        size: _tall,
        account: providerAccountJson(),
        script: (b) => b.on(
          'GET',
          _list,
          (_) => FakeBackend.error(403, 'permission_denied'),
        ),
      );
      expect(
        find.text(
          'Create your provider profile on the Racheeta website to use this area.',
        ),
        findsOneWidget,
      );
    });

    testWidgets('an unknown future status is kept and rendered, never hidden', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/workspace/reservations',
        size: _tall,
        account: providerAccountJson(),
        script: (b) => b.on(
          'GET',
          _list,
          (_) => FakeBackend.json(
            200,
            pageJson([
              providerReservationJson(
                status: 'ARCHIVED',
                patient: 'Odd Patient',
              ),
            ]),
          ),
        ),
      );
      expect(find.text('Odd Patient'), findsOneWidget);
      expect(find.text('Unknown'), findsOneWidget);
    });

    testWidgets('renders Arabic right-to-left', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/workspace/reservations',
        size: _tall,
        language: 'ar',
        account: providerAccountJson(),
        script: (b) => b.on(
          'GET',
          _list,
          (_) => FakeBackend.json(200, pageJson([providerReservationJson()])),
        ),
      );
      expect(find.text('الحجوزات'), findsWidgets);
      expect(find.text('قيد الانتظار'), findsOneWidget);
      expect(
        Directionality.of(tester.element(find.text('Layla Hassan'))),
        TextDirection.rtl,
      );
    });
  });

  group('provider reservation detail', () {
    testWidgets(
      'shows the provider-visible fields and the transition history',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/workspace/reservations/$reservationId',
          size: _tall,
          account: providerAccountJson(),
          script: (b) => b.on(
            'GET',
            _detail,
            (_) => FakeBackend.json(200, {
              ...providerReservationJson(
                status: 'CONFIRMED',
                note: 'knee pain',
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
              // fields the contract does not define must never be rendered
              'patient': {
                'id': patientRecordId,
                'full_name': 'Layla Hassan',
                'email': 'secret@example.com',
                'phone_number': '+9647700000000',
              },
            }),
          ),
        );
        expect(find.text('Layla Hassan'), findsOneWidget);
        expect(find.text('knee pain'), findsOneWidget);
        expect(find.text('Consultation'), findsOneWidget);
        expect(find.textContaining('25,000'), findsOneWidget);
        expect(find.textContaining(_local(5, 9)), findsWidgets);
        expect(find.text('Status history'), findsOneWidget);
        expect(find.textContaining('secret@example.com'), findsNothing);
        expect(find.textContaining('+964'), findsNothing);
      },
    );

    testWidgets(
      'a reservation of another provider is the generic not-found text',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/workspace/reservations/$reservationId',
          size: _tall,
          account: providerAccountJson(),
          script: (b) =>
              b.on('GET', _detail, (_) => FakeBackend.error(404, 'not_found')),
        );
        expect(find.text("We couldn't find that."), findsOneWidget);
        expect(find.byKey(const Key('transition-CONFIRMED')), findsNothing);
      },
    );
  });

  group('transitions: which buttons are offered', () {
    for (final c in [
      ('PENDING', _future, <String>['CONFIRMED', 'REJECTED', 'CANCELLED']),
      ('PENDING', _past, <String>['REJECTED', 'CANCELLED']),
      ('CONFIRMED', _future, <String>['CANCELLED']),
      ('CONFIRMED', _past, <String>['COMPLETED', 'NO_SHOW', 'CANCELLED']),
      ('COMPLETED', _past, <String>[]),
      ('REJECTED', _future, <String>[]),
      ('CANCELLED', _future, <String>[]),
      ('NO_SHOW', _past, <String>[]),
      ('ARCHIVED', _future, <String>[]),
    ]) {
      testWidgets(
        '${c.$1} starting ${c.$2}: ${c.$3.isEmpty ? 'none' : c.$3.join(', ')}',
        (tester) async {
          await pumpPatientApp(
            tester,
            path: '/workspace/reservations/$reservationId',
            size: _tall,
            account: providerAccountJson(),
            script: (b) => b.on(
              'GET',
              _detail,
              (_) => FakeBackend.json(
                200,
                providerReservationJson(status: c.$1, startsAt: c.$2),
              ),
            ),
          );
          for (final target in [
            'CONFIRMED',
            'REJECTED',
            'CANCELLED',
            'COMPLETED',
            'NO_SHOW',
          ]) {
            expect(
              find.byKey(Key('transition-$target')),
              c.$3.contains(target) ? findsOneWidget : findsNothing,
              reason: target,
            );
          }
        },
      );
    }
  });

  group('transitions: acting', () {
    Future<Harness> open(
      WidgetTester tester, {
      String status = 'PENDING',
      String startsAt = _future,
      Responder? transition,
    }) {
      var current = status;
      return pumpPatientApp(
        tester,
        path: '/workspace/reservations/$reservationId',
        size: _tall,
        account: providerAccountJson(),
        script: (b) {
          b.on(
            'GET',
            _detail,
            (_) => FakeBackend.json(
              200,
              providerReservationJson(status: current, startsAt: startsAt),
            ),
          );
          b.on('POST', _transition, (r) {
            final target = (r.body! as Map)['status']! as String;
            if (transition != null) return transition(r);
            current = target;
            return FakeBackend.json(
              200,
              providerReservationJson(status: target, startsAt: startsAt),
            );
          });
        },
      );
    }

    Future<void> tapAndConfirm(
      WidgetTester tester,
      String target, {
      required bool dialog,
      String? dialogAction,
    }) async {
      await tester.tap(find.byKey(Key('transition-$target')));
      await tester.pumpAndSettle();
      if (dialog) {
        expect(find.byType(AlertDialog), findsOneWidget);
        await tester.tap(
          find.descendant(
            of: find.byType(AlertDialog),
            matching: find.text(dialogAction!),
          ),
        );
        await tester.pumpAndSettle();
      }
    }

    for (final c in [
      ('PENDING', _future, 'CONFIRMED', false, null),
      ('PENDING', _future, 'REJECTED', true, 'Reject'),
      ('PENDING', _future, 'CANCELLED', true, 'Cancel booking'),
      ('CONFIRMED', _past, 'COMPLETED', false, null),
      ('CONFIRMED', _past, 'NO_SHOW', true, 'Mark as no-show'),
      ('CONFIRMED', _past, 'CANCELLED', true, 'Cancel booking'),
    ]) {
      testWidgets(
        '${c.$1} → ${c.$3}: one POST with the documented body, then the record is refetched',
        (tester) async {
          final h = await open(tester, status: c.$1, startsAt: c.$2);
          await tapAndConfirm(tester, c.$3, dialog: c.$4, dialogAction: c.$5);
          final posts = h.backend.to('POST', _transition);
          expect(posts, hasLength(1));
          expect(posts.single.body, {'status': c.$3});
          expect(find.text('The booking was updated.'), findsOneWidget);
          expect(h.backend.count('GET', _detail), 2);
          // closed now: nothing further is offered
          expect(find.byKey(Key('transition-${c.$3}')), findsNothing);
        },
      );
    }

    testWidgets(
      'declining the confirmation of a destructive transition sends nothing',
      (tester) async {
        final h = await open(tester);
        await tester.tap(find.byKey(const Key('transition-REJECTED')));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Keep booking'));
        await tester.pumpAndSettle();
        expect(h.backend.count('POST', _transition), 0);
        expect(find.byKey(const Key('booking-message')), findsNothing);
      },
    );

    testWidgets(
      'a refused transition (400 invalid_transition): localized message, true state refetched',
      (tester) async {
        final h = await open(
          tester,
          transition: (_) =>
              FakeBackend.error(400, 'invalid_transition', message: 'raw text'),
        );
        await tapAndConfirm(tester, 'CONFIRMED', dialog: false);
        expect(
          find.text("This booking can't be changed that way right now."),
          findsOneWidget,
        );
        expect(find.textContaining('raw text'), findsNothing);
        expect(h.backend.count('POST', _transition), 1, reason: 'not retried');
        expect(h.backend.count('GET', _detail), 2);
      },
    );

    testWidgets('a 404 on the transition is the generic text and not retried', (
      tester,
    ) async {
      final h = await open(
        tester,
        transition: (_) => FakeBackend.error(404, 'not_found'),
      );
      await tapAndConfirm(tester, 'CONFIRMED', dialog: false);
      expect(find.text("We couldn't find that."), findsWidgets);
      expect(h.backend.count('POST', _transition), 1);
    });

    testWidgets('a network failure is never retried automatically', (
      tester,
    ) async {
      final h = await open(tester, transition: FakeBackend.networkDown);
      await tapAndConfirm(tester, 'CONFIRMED', dialog: false);
      expect(find.textContaining('Could not reach the server'), findsOneWidget);
      await tester.pump(const Duration(seconds: 30));
      expect(h.backend.count('POST', _transition), 1);
    });

    testWidgets(
      'a duplicate tap sends ONE request, shows progress and locks the other actions',
      (tester) async {
        final gate = Completer<void>();
        final h = await open(
          tester,
          transition: (_) async {
            await gate.future;
            return FakeBackend.json(
              200,
              providerReservationJson(status: 'CONFIRMED'),
            );
          },
        );
        await tester.tap(find.byKey(const Key('transition-CONFIRMED')));
        await tester.pump(const Duration(milliseconds: 20));
        expect(find.text('Confirming…'), findsOneWidget);
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        await tester.tap(find.text('Confirming…'), warnIfMissed: false);
        // the other transitions cannot be started while one is running
        expect(
          tester
              .widget<OutlinedButton>(
                find.descendant(
                  of: find.byKey(const Key('transition-REJECTED')),
                  matching: find.byType(OutlinedButton),
                ),
              )
              .onPressed,
          isNull,
        );
        expect(
          tester
              .widget<OutlinedButton>(
                find.descendant(
                  of: find.byKey(const Key('transition-CANCELLED')),
                  matching: find.byType(OutlinedButton),
                ),
              )
              .onPressed,
          isNull,
        );
        await tester.pump(const Duration(milliseconds: 20));
        expect(h.backend.count('POST', _transition), 1);
        gate.complete();
        await tester.pumpAndSettle();
        expect(h.backend.count('POST', _transition), 1);
      },
    );

    testWidgets('the list and the dashboard are reloaded after a transition', (
      tester,
    ) async {
      var status = 'PENDING';
      final h = await pumpPatientApp(
        tester,
        path: '/workspace/reservations',
        size: _tall,
        account: providerAccountJson(),
        script: (b) {
          dashboardsFor(b);
          b
            ..on(
              'GET',
              _list,
              (_) => FakeBackend.json(
                200,
                pageJson([providerReservationJson(status: status)]),
              ),
            )
            ..on(
              'GET',
              _detail,
              (_) => FakeBackend.json(
                200,
                providerReservationJson(status: status),
              ),
            )
            ..on('POST', _transition, (_) {
              status = 'CONFIRMED';
              return FakeBackend.json(
                200,
                providerReservationJson(status: 'CONFIRMED'),
              );
            });
        },
      );
      final router = h.container.read(routerProvider);
      // visit the dashboard once so it is cached
      router.go('/workspace');
      await tester.pumpAndSettle();
      expect(h.backend.count('GET', '/api/v1/dashboards/doctor'), 1);
      router.go('/workspace/reservations');
      await tester.pumpAndSettle();
      expect(h.backend.count('GET', _list), 1);
      expect(find.text('Pending'), findsOneWidget);

      await tester.tap(find.text('Layla Hassan'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('transition-CONFIRMED')));
      await tester.pumpAndSettle();

      router.go('/workspace/reservations');
      await tester.pumpAndSettle();
      expect(
        h.backend.count('GET', _list),
        2,
        reason: 'the cached list was invalidated',
      );
      expect(find.text('Confirmed'), findsOneWidget);
      router.go('/workspace');
      await tester.pumpAndSettle();
      expect(h.backend.count('GET', '/api/v1/dashboards/doctor'), 2);
    });

    testWidgets('Arabic labels and RTL on the detail actions', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/workspace/reservations/$reservationId',
        size: _tall,
        language: 'ar',
        account: providerAccountJson(),
        script: (b) => b.on(
          'GET',
          _detail,
          (_) => FakeBackend.json(200, providerReservationJson()),
        ),
      );
      expect(find.text('تأكيد'), findsOneWidget);
      expect(find.text('رفض'), findsOneWidget);
      expect(find.text('إلغاء الحجز'), findsOneWidget);
      expect(find.text('المريض'), findsOneWidget);
      expect(
        Directionality.of(tester.element(find.text('تأكيد'))),
        TextDirection.rtl,
      );
    });
  });
}
