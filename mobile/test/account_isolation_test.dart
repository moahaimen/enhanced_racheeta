import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart';

/// "Account A's data never appears under account B", proven the hard way: the authenticated
/// account changes through a `/me` refresh while the SAME screen stays mounted (a logout/login
/// would rebuild the route and hide the bug), with B's answer held back so the window in which a
/// stale value could be shown is observable.
const _size = Size(800, 2400);
const _slots = '/api/v1/reservations/provider/availability';
const _services = '/api/v1/providers/me/services';
const _list = '/api/v1/reservations/provider';
const _detail = '/api/v1/reservations/provider/$reservationId';
const _transition = '/api/v1/reservations/provider/$reservationId/transition';

final Map<String, Object?> _a = providerAccountJson(name: 'Provider A');
final Map<String, Object?> _b = providerAccountJson(
  id: otherProviderAccountId,
  name: 'Provider B',
);

void main() {
  group('provider screens: data', () {
    testWidgets(
      'dashboard: A\'s figures disappear at once and B gets only B\'s',
      (tester) async {
        var who = 'A';
        final gateB = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: '/workspace',
          size: _size,
          account: _a,
          script: (b) => b
            ..on(
              'GET',
              '/api/v1/dashboards/',
              (_) => FakeBackend.json(200, {
                'dashboards': ['doctor'],
              }),
            )
            ..on('GET', '/api/v1/dashboards/doctor', (_) async {
              if (who == 'B') await gateB.future;
              return FakeBackend.json(
                200,
                dashboardJson(
                  name: who == 'A' ? 'DASHBOARD OF A' : 'DASHBOARD OF B',
                ),
              );
            }),
        );
        expect(find.text('DASHBOARD OF A'), findsOneWidget);

        who = 'B';
        await switchAccountTo(tester, h, _b);
        expect(
          find.text('DASHBOARD OF A'),
          findsNothing,
          reason: 'while B is loading',
        );
        expect(find.byKey(const Key('dashboard-reservations')), findsNothing);
        expect(find.byType(CircularProgressIndicator), findsOneWidget);

        gateB.complete();
        await tester.pumpAndSettle();
        expect(find.text('DASHBOARD OF A'), findsNothing);
        expect(find.text('DASHBOARD OF B'), findsOneWidget);
      },
    );

    testWidgets(
      'dashboard: a provider who becomes a patient sees nothing of the provider\'s data',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/workspace',
          size: _size,
          account: _a,
          script: (b) => dashboardsFor(
            b,
            dashboard: dashboardJson(name: 'DASHBOARD OF A'),
          ),
        );
        expect(find.text('DASHBOARD OF A'), findsOneWidget);
        await switchAccountTo(
          tester,
          h,
          accountJson(id: otherProviderAccountId),
        );
        await tester.pumpAndSettle();
        expect(find.text('DASHBOARD OF A'), findsNothing);
        expect(
          find.text('This area is for provider accounts.'),
          findsOneWidget,
        );
      },
    );

    testWidgets(
      'reservation list: A\'s bookings disappear at once and are not actionable',
      (tester) async {
        var who = 'A';
        final gateB = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: '/workspace/reservations',
          size: _size,
          account: _a,
          script: (b) => b.on('GET', _list, (_) async {
            if (who == 'B') await gateB.future;
            return FakeBackend.json(
              200,
              pageJson([
                providerReservationJson(
                  patient: who == 'A' ? 'PATIENT OF A' : 'PATIENT OF B',
                ),
              ]),
            );
          }),
        );
        expect(find.text('PATIENT OF A'), findsOneWidget);

        who = 'B';
        await switchAccountTo(tester, h, _b);
        expect(find.text('PATIENT OF A'), findsNothing);
        // nothing of A's is left on screen to tap
        expect(find.text('Layla Hassan'), findsNothing);
        gateB.complete();
        await tester.pumpAndSettle();
        expect(find.text('PATIENT OF A'), findsNothing);
        expect(find.text('PATIENT OF B'), findsOneWidget);
      },
    );

    testWidgets(
      'reservation detail: A\'s booking and its action buttons never reach B',
      (tester) async {
        var who = 'A';
        final gateB = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: '/workspace/reservations/$reservationId',
          size: _size,
          account: _a,
          script: (b) => b.on('GET', _detail, (_) async {
            if (who == 'B') {
              await gateB.future;
              // scoped by the backend: another provider's reservation is a plain 404
              return FakeBackend.error(404, 'not_found');
            }
            return FakeBackend.json(
              200,
              providerReservationJson(
                patient: 'PATIENT OF A',
                note: 'NOTE OF A',
              ),
            );
          }),
        );
        expect(find.text('PATIENT OF A'), findsOneWidget);
        expect(find.byKey(const Key('transition-CONFIRMED')), findsOneWidget);

        who = 'B';
        await switchAccountTo(tester, h, _b);
        expect(
          find.text('PATIENT OF A'),
          findsNothing,
          reason: 'while B is loading',
        );
        expect(find.text('NOTE OF A'), findsNothing);
        expect(find.byKey(const Key('transition-CONFIRMED')), findsNothing);

        gateB.complete();
        await tester.pumpAndSettle();
        expect(find.text("We couldn't find that."), findsOneWidget);
        expect(find.text('PATIENT OF A'), findsNothing);
        expect(find.byKey(const Key('transition-CONFIRMED')), findsNothing);
        expect(h.backend.count('POST', _transition), 0);
      },
    );

    testWidgets('availability list: A\'s slots disappear at once', (
      tester,
    ) async {
      var who = 'A';
      final gateB = Completer<void>();
      final h = await pumpPatientApp(
        tester,
        path: '/workspace/availability',
        size: _size,
        account: _a,
        script: (b) => b.on('GET', _slots, (_) async {
          if (who == 'B') await gateB.future;
          return FakeBackend.json(
            200,
            pageJson([
              ownSlotJson(
                'x',
                '2026-10-05T06:00:00Z',
                title: who == 'A' ? 'SERVICE OF A' : 'SERVICE OF B',
              ),
            ]),
          );
        }),
      );
      expect(find.text('SERVICE OF A'), findsOneWidget);
      who = 'B';
      await switchAccountTo(tester, h, _b);
      expect(find.text('SERVICE OF A'), findsNothing);
      gateB.complete();
      await tester.pumpAndSettle();
      expect(find.text('SERVICE OF B'), findsOneWidget);
    });

    testWidgets(
      'patient reservation detail (11B): A\'s appointment never reaches B while B loads',
      (tester) async {
        var who = 'A';
        final gateB = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: '/reservations/$reservationId',
          size: _size,
          script: (b) =>
              b.on('GET', '/api/v1/reservations/me/$reservationId', (_) async {
                if (who == 'B') {
                  await gateB.future;
                  return FakeBackend.error(404, 'not_found');
                }
                return FakeBackend.json(
                  200,
                  reservationJson(
                    provider: 'DOCTOR OF PATIENT A',
                    note: 'NOTE OF A',
                  ),
                );
              }),
        );
        expect(find.text('DOCTOR OF PATIENT A'), findsOneWidget);

        who = 'B';
        await switchAccountTo(
          tester,
          h,
          accountJson(
            id: '99999999-9999-4999-8999-999999999999',
            name: 'Patient B',
          ),
        );
        expect(
          find.text('DOCTOR OF PATIENT A'),
          findsNothing,
          reason: 'while B is loading',
        );
        expect(find.text('NOTE OF A'), findsNothing);
        expect(find.text('Cancel appointment'), findsNothing);

        gateB.complete();
        await tester.pumpAndSettle();
        expect(find.text("We couldn't find that."), findsOneWidget);
        expect(find.text('DOCTOR OF PATIENT A'), findsNothing);
      },
    );
  });

  group('provider screens: mutations in flight', () {
    testWidgets(
      'a late SUCCESS of A\'s transition is never shown to B and invalidates nothing',
      (tester) async {
        final postGate = Completer<void>();
        var who = 'A';
        final h = await pumpPatientApp(
          tester,
          path: '/workspace/reservations/$reservationId',
          size: _size,
          account: _a,
          script: (b) {
            b.on('GET', _detail, (_) {
              if (who == 'B') return FakeBackend.error(404, 'not_found');
              return FakeBackend.json(200, providerReservationJson());
            });
            b.on('POST', _transition, (_) async {
              await postGate.future;
              return FakeBackend.json(
                200,
                providerReservationJson(status: 'CONFIRMED'),
              );
            });
          },
        );
        await tester.tap(find.byKey(const Key('transition-CONFIRMED')));
        await tester.pump(const Duration(milliseconds: 30));
        expect(h.backend.count('POST', _transition), 1);

        who = 'B';
        await switchAccountTo(tester, h, _b);
        await tester.pumpAndSettle();
        final detailGets = h.backend.count('GET', _detail);
        expect(find.text("We couldn't find that."), findsOneWidget);

        postGate.complete();
        await tester.pumpAndSettle();
        expect(find.text('The booking was updated.'), findsNothing);
        expect(
          find.text("We couldn't find that."),
          findsOneWidget,
          reason: 'B still sees only B\'s state',
        );
        expect(
          h.backend.count('GET', _detail),
          detailGets,
          reason: 'A\'s completed mutation must not invalidate/refetch anything for B',
        );
      },
    );

    testWidgets('a late ERROR of A\'s transition is never shown to B', (
      tester,
    ) async {
      final postGate = Completer<void>();
      var who = 'A';
      final h = await pumpPatientApp(
        tester,
        path: '/workspace/reservations/$reservationId',
        size: _size,
        account: _a,
        script: (b) {
          b.on('GET', _detail, (_) {
            if (who == 'B') return FakeBackend.error(404, 'not_found');
            return FakeBackend.json(200, providerReservationJson());
          });
          b.on('POST', _transition, (_) async {
            await postGate.future;
            return FakeBackend.error(400, 'invalid_transition');
          });
        },
      );
      await tester.tap(find.byKey(const Key('transition-CONFIRMED')));
      await tester.pump(const Duration(milliseconds: 30));

      who = 'B';
      await switchAccountTo(tester, h, _b);
      await tester.pumpAndSettle();
      postGate.complete();
      await tester.pumpAndSettle();
      expect(
        find.text("This booking can't be changed that way right now."),
        findsNothing,
      );
      expect(find.byKey(const Key('booking-message')), findsNothing);
    });

    testWidgets(
      'a late SUCCESS of A\'s slot creation is never shown to B; the form is reset',
      (tester) async {
        final postGate = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: '/workspace/availability/new',
          size: _size,
          account: _a,
          script: (b) => b
            ..on(
              'GET',
              _services,
              (_) => FakeBackend.json(200, [ownServiceJson()]),
            )
            ..on('POST', _slots, (_) async {
              await postGate.future;
              return FakeBackend.json(
                201,
                ownSlotJson('new', '2026-10-04T06:00:00Z'),
              );
            }),
        );
        await _fill(tester);
        await tester.tap(find.byKey(const Key('slot-create')));
        await tester.pump(const Duration(milliseconds: 30));
        expect(h.backend.count('POST', _slots), 1);

        await switchAccountTo(tester, h, _b);
        await tester.pumpAndSettle();
        // B starts from an empty form
        expect(
          tester
              .widget<FilledButton>(
                find.descendant(
                  of: find.byKey(const Key('slot-create')),
                  matching: find.byType(FilledButton),
                ),
              )
              .onPressed,
          isNull,
        );
        expect(find.byKey(const Key('slot-summary')), findsNothing);
        expect(
          find.text('Choose a service, a date and a start time.'),
          findsOneWidget,
        );

        postGate.complete();
        await tester.pumpAndSettle();
        expect(find.text('Availability added.'), findsNothing);
        expect(find.byKey(const Key('slot-form-message')), findsNothing);
      },
    );

    testWidgets('a late ERROR of A\'s slot creation is never shown to B', (
      tester,
    ) async {
      final postGate = Completer<void>();
      final h = await pumpPatientApp(
        tester,
        path: '/workspace/availability/new',
        size: _size,
        account: _a,
        script: (b) => b
          ..on(
            'GET',
            _services,
            (_) => FakeBackend.json(200, [ownServiceJson()]),
          )
          ..on('POST', _slots, (_) async {
            await postGate.future;
            return FakeBackend.error(409, 'slot_conflict');
          }),
      );
      await _fill(tester);
      await tester.tap(find.byKey(const Key('slot-create')));
      await tester.pump(const Duration(milliseconds: 30));

      await switchAccountTo(tester, h, _b);
      await tester.pumpAndSettle();
      postGate.complete();
      await tester.pumpAndSettle();
      expect(
        find.text('This time overlaps another active time.'),
        findsNothing,
      );
      expect(find.byKey(const Key('slot-form-message')), findsNothing);
    });

    testWidgets(
      'A\'s typed slot choices and messages do not survive an account switch',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/workspace/availability/new',
          size: _size,
          account: _a,
          script: (b) => b
            ..on(
              'GET',
              _services,
              (_) => FakeBackend.json(200, [ownServiceJson()]),
            )
            ..on(
              'POST',
              _slots,
              (_) => FakeBackend.error(409, 'slot_conflict'),
            ),
        );
        await _fill(tester);
        await tester.tap(find.byKey(const Key('slot-create')));
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('slot-form-message')), findsOneWidget);

        await switchAccountTo(tester, h, _b);
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('slot-form-message')), findsNothing);
        expect(find.byKey(const Key('slot-summary')), findsNothing);
        expect(find.text('Choose a date'), findsOneWidget);
        expect(find.text('Choose a start time'), findsOneWidget);
      },
    );

    testWidgets('a late success of A\'s slot removal is never shown to B', (
      tester,
    ) async {
      final deleteGate = Completer<void>();
      final h = await pumpPatientApp(
        tester,
        path: '/workspace/availability',
        size: _size,
        account: _a,
        script: (b) => b
          ..on(
            'GET',
            _slots,
            (_) => FakeBackend.json(
              200,
              pageJson([ownSlotJson('x', '2026-10-05T06:00:00Z')]),
            ),
          )
          ..on('DELETE', '$_slots/x', (_) async {
            await deleteGate.future;
            return FakeBackend.noContent();
          }),
      );
      await tester.tap(find.text('Remove'));
      await tester.pumpAndSettle();
      await tester.tap(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.text('Remove'),
        ),
      );
      await tester.pump(const Duration(milliseconds: 30));
      expect(h.backend.count('DELETE', '$_slots/x'), 1);

      await switchAccountTo(tester, h, _b);
      await tester.pumpAndSettle();
      final gets = h.backend.count('GET', _slots);
      deleteGate.complete();
      await tester.pumpAndSettle();
      expect(find.text('The time was removed.'), findsNothing);
      expect(
        h.backend.count('GET', _slots),
        gets,
        reason: 'nothing invalidated for B',
      );
    });
  });
}

Future<void> _fill(WidgetTester tester) async {
  await tester.tap(find.byKey(const Key('slot-service')));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Consultation · 30 min').last);
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(const Key('slot-date')));
  await tester.pumpAndSettle();
  await tester.tap(find.text('OK'));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(const Key('slot-time')));
  await tester.pumpAndSettle();
  await tester.tap(find.text('OK'));
  await tester.pumpAndSettle();
}
