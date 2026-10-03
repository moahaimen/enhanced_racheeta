import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/intl.dart' show DateFormat;
import 'package:racheeta_mobile/app/router.dart';
import 'package:racheeta_mobile/features/auth/application/providers.dart';

import 'support/fake_backend.dart';
import 'support/patient_support.dart';

const _bookPath = '/providers/$providerId/book/$serviceId';
const _providerPath = '/api/v1/providers/$providerId';
const _availabilityPath = '/api/v1/providers/$providerId/availability';
const _create = '/api/v1/reservations';
const _tall = Size(800, 1800);

// 2026-10-04 06:00Z / 07:00Z = 09:00 / 10:00 local; 21:30Z = 00:30 the NEXT local day (UTC+3).
final List<Map<String, Object?>> _slots = [
  slotJson('slot-1', '2026-10-04T06:00:00Z'),
  slotJson('slot-2', '2026-10-04T07:00:00Z'),
  slotJson('slot-3', '2026-10-04T21:30:00Z'),
];

String _day(int day) => DateFormat.MMMEd('en').format(DateTime(2026, 10, day));
String _time(int day, int hour, [int minute = 0]) =>
    DateFormat.jm('en').format(DateTime(2026, 10, day, hour, minute));

void _script(
  FakeBackend b, {
  List<Map<String, Object?>>? slots,
  Responder? create,
}) {
  b
    ..on('GET', _providerPath, (_) => FakeBackend.json(200, providerJson()))
    ..on(
      'GET',
      _availabilityPath,
      (_) => FakeBackend.json(200, slots ?? _slots),
    );
  if (create != null) b.on('POST', _create, create);
}

Finder _confirmButton() => find.widgetWithText(FilledButton, 'Confirm booking');

Future<void> _pick(WidgetTester tester, String time) async {
  await tester.tap(find.text(time));
  await tester.pump();
}

void main() {
  group('booking: availability', () {
    testWidgets(
      'asks the backend for the service within the 30-day UTC window',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: _bookPath,
          size: _tall,
          script: _script,
        );
        final request = h.backend.to('GET', _availabilityPath).single;
        expect(request.query, {
          'service': serviceId,
          'from': '2026-10-03T09:00:00.000Z',
          'to': '2026-11-02T09:00:00.000Z',
        });
        expect(find.text('Consultation'), findsOneWidget);
        expect(find.textContaining('30 min'), findsOneWidget);
      },
    );

    testWidgets(
      'slots are grouped by the LOCAL calendar day (a 21:30Z slot is next day)',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: _bookPath,
          size: _tall,
          script: _script,
        );
        expect(find.text(_day(4)), findsOneWidget);
        expect(find.text(_day(5)), findsOneWidget);
        // first day selected: only its two slots
        expect(find.text(_time(4, 9)), findsOneWidget);
        expect(find.text(_time(4, 10)), findsOneWidget);
        expect(find.text(_time(5, 0, 30)), findsNothing);

        await tester.tap(find.text(_day(5)));
        await tester.pump();
        expect(find.text(_time(5, 0, 30)), findsOneWidget);
        expect(find.text(_time(4, 9)), findsNothing);
        expect(
          find.text("Times are shown in your device's time zone."),
          findsOneWidget,
        );
      },
    );

    testWidgets(
      'selecting a time enables confirm and summarises the local time',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: _bookPath,
          size: _tall,
          script: _script,
        );
        expect(tester.widget<FilledButton>(_confirmButton()).onPressed, isNull);
        expect(find.text('Select a time to continue.'), findsOneWidget);
        await _pick(tester, _time(4, 9));
        expect(
          tester.widget<FilledButton>(_confirmButton()).onPressed,
          isNotNull,
        );
        expect(find.byKey(const Key('booking-summary')), findsOneWidget);
        expect(
          tester.widget<Text>(find.byKey(const Key('booking-summary'))).data,
          contains('9:00'),
        );
      },
    );

    testWidgets(
      'no availability is explained and refresh asks the backend again',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: _bookPath,
          size: _tall,
          script: (b) => _script(b, slots: const []),
        );
        expect(
          find.text('No appointments are available right now.'),
          findsOneWidget,
        );
        expect(_confirmButton(), findsNothing);
        await tester.tap(find.text('Refresh availability'));
        await tester.pumpAndSettle();
        expect(h.backend.count('GET', _availabilityPath), 2);
      },
    );

    testWidgets(
      'a failing availability call shows a safe message and retry works',
      (tester) async {
        var fail = true;
        final h = await pumpPatientApp(
          tester,
          path: _bookPath,
          size: _tall,
          script: (b) => b
            ..on(
              'GET',
              _providerPath,
              (_) => FakeBackend.json(200, providerJson()),
            )
            ..on(
              'GET',
              _availabilityPath,
              (_) => fail
                  ? FakeBackend.error(
                      500,
                      'server_error',
                      message: 'Traceback x',
                    )
                  : FakeBackend.json(200, _slots),
            ),
        );
        expect(
          find.textContaining('Something went wrong on our side'),
          findsOneWidget,
        );
        expect(find.textContaining('Traceback'), findsNothing);
        fail = false;
        await tester.tap(find.text('Try again'));
        await tester.pumpAndSettle();
        expect(find.text(_day(4)), findsOneWidget);
        expect(h.backend.count('GET', _availabilityPath), 2);
      },
    );

    testWidgets('an unknown service id is the generic not-found text', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path:
            '/providers/$providerId/book/00000000-0000-4000-8000-000000000000',
        size: _tall,
        script: _script,
      );
      expect(find.text("We couldn't find that."), findsOneWidget);
    });

    testWidgets('only patient accounts can book', (tester) async {
      final h = await pumpPatientApp(
        tester,
        path: _bookPath,
        size: _tall,
        account: {
          ...accountJson(role: 'PROVIDER'),
          'permissions': <String>['accounts.view_self'],
        },
        script: _script,
      );
      expect(
        find.text('Only patient accounts can book appointments.'),
        findsOneWidget,
      );
      expect(h.backend.count('POST', _create), 0);
    });
  });

  group('booking: submit', () {
    testWidgets(
      'success sends exactly the documented body once and shows the result',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: _bookPath,
          size: _tall,
          script: (b) => _script(
            b,
            create: (_) => FakeBackend.json(
              201,
              reservationJson(
                startsAt: '2026-10-04T06:00:00Z',
                note: 'knee pain',
              ),
            ),
          ),
        );
        await _pick(tester, _time(4, 9));
        await tester.enterText(find.byType(TextField), '  knee pain  ');
        await tester.tap(_confirmButton());
        await tester.pumpAndSettle();

        final posts = h.backend.to('POST', _create);
        expect(posts, hasLength(1));
        expect(posts.single.body, {
          'availability_slot': 'slot-1',
          'patient_note': 'knee pain',
        });
        expect(find.byKey(const Key('booking-success')), findsOneWidget);
        expect(find.text('Booking sent'), findsOneWidget);
      },
    );

    testWidgets('an empty note is not sent', (tester) async {
      final h = await pumpPatientApp(
        tester,
        path: _bookPath,
        size: _tall,
        script: (b) =>
            _script(b, create: (_) => FakeBackend.json(201, reservationJson())),
      );
      await _pick(tester, _time(4, 10));
      await tester.tap(_confirmButton());
      await tester.pumpAndSettle();
      expect(h.backend.to('POST', _create).single.body, {
        'availability_slot': 'slot-2',
      });
    });

    testWidgets(
      'a double tap while pending sends ONE request and shows progress',
      (tester) async {
        final gate = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: _bookPath,
          size: _tall,
          script: (b) => _script(
            b,
            create: (_) async {
              await gate.future;
              return FakeBackend.json(201, reservationJson());
            },
          ),
        );
        await _pick(tester, _time(4, 9));
        await tester.tap(_confirmButton());
        await tester.pump();
        expect(find.text('Booking…'), findsOneWidget);
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        await tester.tap(find.text('Booking…'), warnIfMissed: false);
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 20));
        expect(h.backend.count('POST', _create), 1);
        gate.complete();
        await tester.pumpAndSettle();
        expect(h.backend.count('POST', _create), 1);
        expect(find.byKey(const Key('booking-success')), findsOneWidget);
      },
    );

    testWidgets(
      'a taken slot (409): localized banner, selection cleared, list refetched, no retry',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: _bookPath,
          size: _tall,
          script: (b) => _script(
            b,
            create: (_) => FakeBackend.error(409, 'slot_unavailable'),
          ),
        );
        await _pick(tester, _time(4, 9));
        await tester.tap(_confirmButton());
        await tester.pumpAndSettle();

        expect(
          find.text(
            'That time is no longer available. The list has been refreshed; please pick another time.',
          ),
          findsOneWidget,
        );
        expect(find.text('Select a time to continue.'), findsOneWidget);
        expect(tester.widget<FilledButton>(_confirmButton()).onPressed, isNull);
        expect(h.backend.count('GET', _availabilityPath), 2);
        await tester.pump(const Duration(seconds: 5));
        expect(
          h.backend.count('POST', _create),
          1,
          reason: 'never auto-retried',
        );
      },
    );

    testWidgets('slot_conflict is the same taken-slot flow', (tester) async {
      final h = await pumpPatientApp(
        tester,
        path: _bookPath,
        size: _tall,
        script: (b) =>
            _script(b, create: (_) => FakeBackend.error(409, 'slot_conflict')),
      );
      await _pick(tester, _time(4, 9));
      await tester.tap(_confirmButton());
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('booking-banner')), findsOneWidget);
      expect(h.backend.count('GET', _availabilityPath), 2);
    });

    testWidgets('provider/service unavailable have their own safe messages', (
      tester,
    ) async {
      var code = 'provider_unavailable';
      await pumpPatientApp(
        tester,
        path: _bookPath,
        size: _tall,
        script: (b) => _script(b, create: (_) => FakeBackend.error(409, code)),
      );
      await _pick(tester, _time(4, 9));
      await tester.tap(_confirmButton());
      await tester.pumpAndSettle();
      expect(
        find.text('This provider is not accepting bookings right now.'),
        findsOneWidget,
      );
      code = 'service_unavailable';
      await tester.tap(_confirmButton());
      await tester.pumpAndSettle();
      expect(
        find.text('This service is not available for booking right now.'),
        findsOneWidget,
      );
    });

    testWidgets('a note over 1000 characters is blocked before any request', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: _bookPath,
        size: _tall,
        script: (b) =>
            _script(b, create: (_) => FakeBackend.json(201, reservationJson())),
      );
      await _pick(tester, _time(4, 9));
      await tester.enterText(find.byType(TextField), 'x' * 1001);
      await tester.tap(_confirmButton());
      await tester.pumpAndSettle();
      expect(
        find.text('The note must be at most 1000 characters.'),
        findsOneWidget,
      );
      expect(h.backend.count('POST', _create), 0);

      await tester.enterText(find.byType(TextField), 'x' * 1000);
      await tester.tap(_confirmButton());
      await tester.pumpAndSettle();
      expect(h.backend.count('POST', _create), 1, reason: '1000 is allowed');
    });

    testWidgets('the backend note validation message is shown on the field', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: _bookPath,
        size: _tall,
        script: (b) => _script(
          b,
          create: (_) => FakeBackend.error(
            400,
            'validation_error',
            message: 'Invalid input.',
            details: {
              'patient_note': [
                'Ensure this field has no more than 1000 characters.',
              ],
            },
          ),
        ),
      );
      await _pick(tester, _time(4, 9));
      await tester.tap(_confirmButton());
      await tester.pumpAndSettle();
      expect(
        find.text('Ensure this field has no more than 1000 characters.'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('booking-banner')), findsNothing);
    });

    testWidgets('403 shows the forbidden message and does not retry', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: _bookPath,
        size: _tall,
        script: (b) => _script(
          b,
          create: (_) => FakeBackend.error(403, 'permission_denied'),
        ),
      );
      await _pick(tester, _time(4, 9));
      await tester.tap(_confirmButton());
      await tester.pumpAndSettle();
      expect(find.text('You are not allowed to do this.'), findsOneWidget);
      expect(h.backend.count('POST', _create), 1);
    });

    testWidgets(
      'a network failure is never retried automatically; the user can try again',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: _bookPath,
          size: _tall,
          script: (b) => _script(b, create: FakeBackend.networkDown),
        );
        await _pick(tester, _time(4, 9));
        await tester.tap(_confirmButton());
        await tester.pumpAndSettle();
        expect(
          find.textContaining('Could not reach the server'),
          findsOneWidget,
        );
        await tester.pump(const Duration(seconds: 30));
        expect(h.backend.count('POST', _create), 1);
        // The selection is kept so a deliberate second tap is possible.
        await tester.tap(_confirmButton());
        await tester.pumpAndSettle();
        expect(h.backend.count('POST', _create), 2);
      },
    );

    testWidgets(
      'after a booking the list and availability are reloaded from the backend',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          size: _tall,
          script: (b) {
            _script(b, create: (_) => FakeBackend.json(201, reservationJson()));
            b
              ..on(
                'GET',
                '/api/v1/reservations/me',
                (_) => FakeBackend.json(200, pageJson([reservationJson()])),
              )
              ..on(
                'GET',
                '/api/v1/reservations/me/$reservationId',
                (_) => FakeBackend.json(200, reservationJson()),
              );
          },
        );
        final router = h.container.read(routerProvider);
        router.go('/reservations');
        await tester.pumpAndSettle();
        expect(h.backend.count('GET', '/api/v1/reservations/me'), 1);

        router.go(_bookPath);
        await tester.pumpAndSettle();
        await _pick(tester, _time(4, 9));
        await tester.tap(_confirmButton());
        await tester.pumpAndSettle();
        await tester.tap(find.text('View appointment'));
        await tester.pumpAndSettle();
        expect(
          h.backend.count('GET', '/api/v1/reservations/me/$reservationId'),
          1,
        );

        router.go('/reservations');
        await tester.pumpAndSettle();
        expect(
          h.backend.count('GET', '/api/v1/reservations/me'),
          2,
          reason: 'the cached list was invalidated by the booking',
        );
      },
    );
  });

  group('booking: account isolation', () {
    // The widget tree (and this page) stays put: only the authenticated account changes, via a
    // `/me` refresh that now answers as account B. Logging out and in would rebuild the route and
    // hide the bug.
    const accountB = '99999999-9999-4999-8999-999999999999';

    Future<void> switchToB(WidgetTester tester, Harness h) async {
      h.backend.on(
        'GET',
        '/api/v1/me',
        (_) =>
            FakeBackend.json(200, accountJson(id: accountB, name: 'Account B')),
      );
      await tester.runAsync(
        () => h.container
            .read(sessionControllerProvider.notifier)
            .refreshAccount(),
      );
      await tester.pump(const Duration(milliseconds: 50));
      await tester.pump(const Duration(milliseconds: 50));
    }

    testWidgets(
      "account A's finished booking is neither visible nor actionable for account B",
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: _bookPath,
          size: _tall,
          script: (b) => _script(
            b,
            create: (_) => FakeBackend.json(201, reservationJson()),
          ),
        );
        await _pick(tester, _time(4, 9));
        await tester.tap(_confirmButton());
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('booking-success')), findsOneWidget);
        expect(find.text('View appointment'), findsOneWidget);
        expect(
          h.container.read(routerProvider).state.matchedLocation,
          _bookPath,
        );

        await switchToB(tester, h);

        // still the same page, but A's result is gone and cannot be acted on
        expect(
          h.container.read(routerProvider).state.matchedLocation,
          _bookPath,
        );
        expect(find.byKey(const Key('booking-success')), findsNothing);
        expect(find.text('Booking sent'), findsNothing);
        expect(find.text('View appointment'), findsNothing);
        expect(find.textContaining(reservationId), findsNothing);
        // B gets a fresh booking form (availability reloaded for B), nothing preselected
        await tester.pumpAndSettle();
        expect(_confirmButton(), findsOneWidget);
        expect(tester.widget<FilledButton>(_confirmButton()).onPressed, isNull);
        expect(find.text('Select a time to continue.'), findsOneWidget);
        expect(find.byKey(const Key('booking-summary')), findsNothing);
        expect(
          h.backend.count('POST', _create),
          1,
          reason: 'nothing resubmitted',
        );
      },
    );

    testWidgets("account A's selection, note and error never reach account B", (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: _bookPath,
        size: _tall,
        script: (b) => _script(
          b,
          create: (_) => FakeBackend.error(409, 'slot_unavailable'),
        ),
      );
      await _pick(tester, _time(4, 9));
      await tester.enterText(find.byType(TextField), 'private note of A');
      await tester.tap(_confirmButton());
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('booking-banner')), findsOneWidget);
      await _pick(tester, _time(4, 10));
      expect(find.byKey(const Key('booking-summary')), findsOneWidget);

      await switchToB(tester, h);
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('booking-banner')), findsNothing);
      expect(find.byKey(const Key('booking-summary')), findsNothing);
      expect(find.text('private note of A'), findsNothing);
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.text,
        isEmpty,
      );
      expect(tester.widget<FilledButton>(_confirmButton()).onPressed, isNull);
    });

    testWidgets(
      'a booking that completes after the account changed is not shown to the new account',
      (tester) async {
        final gate = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: _bookPath,
          size: _tall,
          script: (b) => _script(
            b,
            create: (_) async {
              await gate.future;
              return FakeBackend.json(201, reservationJson());
            },
          ),
        );
        await _pick(tester, _time(4, 9));
        await tester.tap(_confirmButton());
        await tester.pump(const Duration(milliseconds: 20));

        await switchToB(tester, h);
        gate.complete();
        await tester.pumpAndSettle();

        expect(find.byKey(const Key('booking-success')), findsNothing);
        expect(find.text('View appointment'), findsNothing);
      },
    );
  });

  group('booking: Arabic', () {
    testWidgets('renders right-to-left Arabic copy and the same grouping', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: _bookPath,
        size: _tall,
        language: 'ar',
        script: _script,
      );
      expect(find.text('اختر اليوم'), findsOneWidget);
      expect(find.text('تأكيد الحجز'), findsOneWidget);
      expect(find.text('اختر وقتاً للمتابعة.'), findsOneWidget);
      expect(
        find.text('تُعرض الأوقات حسب المنطقة الزمنية لجهازك.'),
        findsOneWidget,
      );
      final context = tester.element(find.text('اختر اليوم'));
      expect(Directionality.of(context), TextDirection.rtl);
      // two day chips: the midnight-crossing slot is the second day
      expect(find.byType(ChoiceChip), findsNWidgets(2 + 2));
    });
  });
}
