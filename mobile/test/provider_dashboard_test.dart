import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/intl.dart' show DateFormat;
import 'package:racheeta_mobile/app/router.dart';

import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart';

const _index = '/api/v1/dashboards/';
const _doctor = '/api/v1/dashboards/doctor';
const _facility = '/api/v1/dashboards/facility';
const _tall = Size(800, 2400);

Finder _in(String key, String text) =>
    find.descendant(of: find.byKey(Key(key)), matching: find.text(text));

void main() {
  group('dashboard: content', () {
    testWidgets(
      'a practitioner sees exactly the figures the backend returned',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/workspace',
          size: _tall,
          account: providerAccountJson(),
          script: (b) => dashboardsFor(b),
        );
        // one index request from Home's Explore section, one from the dashboard itself
        expect(h.backend.count('GET', _index), 2);
        expect(h.backend.count('GET', _doctor), 1);
        expect(h.backend.count('GET', _facility), 0);

        // profile
        expect(_in('dashboard-profile', 'Dr. Sara Ahmed'), findsOneWidget);
        expect(_in('dashboard-profile', 'Doctor'), findsOneWidget);
        expect(_in('dashboard-profile', 'Verified'), findsOneWidget);
        expect(_in('dashboard-profile', 'Visible to patients'), findsOneWidget);
        // reservations: total, upcoming and the per-status counts
        expect(_in('dashboard-reservations', '9'), findsOneWidget);
        expect(
          _in('dashboard-reservations', '3'),
          findsNWidgets(2),
        ); // upcoming + CONFIRMED
        expect(_in('dashboard-reservations', 'Pending'), findsOneWidget);
        expect(_in('dashboard-reservations', 'No show'), findsOneWidget);
        // upcoming appointment: patient, service, local time, status
        expect(_in('dashboard-upcoming', 'Layla Hassan'), findsOneWidget);
        expect(_in('dashboard-upcoming', 'Confirmed'), findsOneWidget);
        // reviews, offers, unread
        expect(_in('dashboard-reviews', '4.5 · 6 reviews'), findsOneWidget);
        expect(_in('dashboard-offers', 'Running now'), findsOneWidget);
        expect(_in('dashboard-unread', '7'), findsOneWidget);
        expect(_in('dashboard-unread', '2'), findsOneWidget);
        // practitioners are a facility-only block
        expect(find.byKey(const Key('dashboard-practitioners')), findsNothing);
        // nothing invented
        expect(find.textContaining('Revenue'), findsNothing);
        expect(find.textContaining('Profile views'), findsNothing);
        expect(find.textContaining('Earnings'), findsNothing);
      },
    );

    testWidgets(
      'a facility sees its own dashboard with the membership counts',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/workspace',
          size: _tall,
          account: providerAccountJson(name: 'Al Noor Clinic'),
          script: (b) => dashboardsFor(
            b,
            facility: true,
            dashboard: dashboardJson(facility: true, name: 'Al Noor Clinic'),
          ),
        );
        expect(h.backend.count('GET', _facility), 1);
        expect(h.backend.count('GET', _doctor), 0);
        expect(_in('dashboard-profile', 'Al Noor Clinic'), findsOneWidget);
        expect(_in('dashboard-profile', 'Medical center'), findsOneWidget);
        expect(_in('dashboard-practitioners', 'Active'), findsOneWidget);
        expect(_in('dashboard-practitioners', '5'), findsOneWidget);
        expect(
          _in('dashboard-practitioners', 'Incoming requests'),
          findsOneWidget,
        );
        expect(
          _in('dashboard-practitioners', 'Outgoing invitations'),
          findsOneWidget,
        );
        // no facility-wide reservation aggregation is invented: the counts are the backend's
        expect(_in('dashboard-reservations', '9'), findsOneWidget);
      },
    );

    testWidgets(
      'the server decides the dashboard: facility wins when both are listed',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/workspace',
          size: _tall,
          account: providerAccountJson(),
          script: (b) =>
              dashboardsFor(b, facility: true, index: ['doctor', 'facility']),
        );
        expect(h.backend.count('GET', _facility), 1);
        expect(h.backend.count('GET', _doctor), 0);
      },
    );

    testWidgets(
      'no reviews and no upcoming appointments have explicit empty states',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/workspace',
          size: _tall,
          account: providerAccountJson(),
          script: (b) => dashboardsFor(
            b,
            dashboard: dashboardJson(
              average: null,
              reviews: 0,
              upcomingList: [],
              total: 0,
              upcoming: 0,
            ),
          ),
        );
        expect(find.text('No upcoming appointments.'), findsOneWidget);
        expect(_in('dashboard-reviews', 'No reviews yet'), findsOneWidget);
        expect(find.textContaining('★'), findsNothing);
      },
    );

    testWidgets(
      'upcoming appointment times are shown in the device-local time',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/workspace',
          size: _tall,
          account: providerAccountJson(),
          script: (b) => dashboardsFor(b),
        );
        // 06:00Z is 09:00 for the UTC+3 reader; the raw UTC clock value is never printed.
        final local = DateFormat.jm('en').format(DateTime(2026, 10, 5, 9));
        final utc = DateFormat.jm('en').format(DateTime(2026, 10, 5, 6));
        expect(find.textContaining(local), findsOneWidget);
        expect(find.textContaining(utc), findsNothing);
        expect(
          find.text("Times are shown in your device's time zone."),
          findsOneWidget,
        );
      },
    );

    testWidgets('an upcoming appointment opens its booking', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/workspace',
        size: _tall,
        account: providerAccountJson(),
        script: (b) {
          dashboardsFor(b);
          b.on(
            'GET',
            '/api/v1/reservations/provider/$reservationId',
            (_) => FakeBackend.json(
              200,
              providerReservationJson(status: 'CONFIRMED'),
            ),
          );
        },
      );
      await tester.tap(find.text('Layla Hassan'));
      await tester.pumpAndSettle();
      expect(find.text('Booking'), findsWidgets);
      expect(find.text('Patient'), findsOneWidget);
    });
  });

  group('dashboard: loading, errors and refresh', () {
    testWidgets('shows loading, then the data', (tester) async {
      final gate = Completer<void>();
      final h = await pumpPatientApp(
        tester,
        size: _tall,
        account: providerAccountJson(),
        script: (b) {
          dashboardsFor(b);
          b.on('GET', _doctor, (_) async {
            await gate.future;
            return FakeBackend.json(200, dashboardJson());
          });
        },
      );
      h.container.read(routerProvider).go('/workspace');
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      gate.complete();
      await tester.pumpAndSettle();
      expect(_in('dashboard-profile', 'Dr. Sara Ahmed'), findsOneWidget);
    });

    testWidgets('a failure shows a safe message and Try again recovers', (
      tester,
    ) async {
      var fail = true;
      final h = await pumpPatientApp(
        tester,
        path: '/workspace',
        size: _tall,
        account: providerAccountJson(),
        script: (b) {
          dashboardsFor(b);
          b.on(
            'GET',
            _doctor,
            (_) => fail
                ? FakeBackend.error(
                    500,
                    'server_error',
                    message: 'Traceback: secret',
                  )
                : FakeBackend.json(200, dashboardJson()),
          );
        },
      );
      expect(
        find.textContaining('Something went wrong on our side'),
        findsOneWidget,
      );
      expect(find.textContaining('secret'), findsNothing);
      fail = false;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(_in('dashboard-profile', 'Dr. Sara Ahmed'), findsOneWidget);
      expect(h.backend.count('GET', _doctor), 2);
    });

    testWidgets('a network failure maps to the offline message', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/workspace',
        size: _tall,
        account: providerAccountJson(),
        script: (b) => b.on('GET', _index, FakeBackend.networkDown),
      );
      expect(find.textContaining('Could not reach the server'), findsOneWidget);
    });

    testWidgets(
      'an account without a provider profile (403) gets the guidance text',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/workspace',
          size: _tall,
          account: providerAccountJson(),
          script: (b) => b.on(
            'GET',
            _index,
            (_) => FakeBackend.error(403, 'permission_denied'),
          ),
        );
        expect(
          find.text(
            'Create your provider profile on the Racheeta website to use this area.',
          ),
          findsOneWidget,
        );
      },
    );

    testWidgets(
      'no provider dashboard in the index means no dashboard request at all',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/workspace',
          size: _tall,
          account: providerAccountJson(),
          script: (b) => dashboardsFor(b, index: ['patient']),
        );
        expect(
          find.text(
            'Create your provider profile on the Racheeta website to use this area.',
          ),
          findsOneWidget,
        );
        expect(h.backend.count('GET', _doctor), 0);
        expect(h.backend.count('GET', _facility), 0);
      },
    );

    testWidgets('pull to refresh reloads from the backend', (tester) async {
      final h = await pumpPatientApp(
        tester,
        path: '/workspace',
        size: const Size(800, 700),
        account: providerAccountJson(),
        script: (b) => dashboardsFor(b),
      );
      expect(h.backend.count('GET', _doctor), 1);
      final indexBefore = h.backend.count('GET', _index);
      await tester.fling(find.byType(ListView), const Offset(0, 400), 1000);
      await tester.pumpAndSettle();
      expect(h.backend.count('GET', _doctor), 2);
      expect(h.backend.count('GET', _index), indexBefore + 1);
    });
  });

  group('dashboard: role and capability isolation', () {
    testWidgets(
      'a provider sees the three workspace destinations and no patient ones',
      (tester) async {
        await pumpPatientApp(
          tester,
          size: const Size(420, 900),
          account: providerAccountJson(),
          script: (b) => dashboardsFor(b),
        );
        final bar = find.byType(NavigationBar);
        for (final label in [
          'Home',
          'Dashboard',
          'Availability',
          'Bookings',
          'Account',
        ]) {
          expect(
            find.descendant(of: bar, matching: find.text(label)),
            findsOneWidget,
            reason: label,
          );
        }
        expect(
          find.descendant(of: bar, matching: find.text('Find care')),
          findsNothing,
        );
        expect(
          find.descendant(of: bar, matching: find.text('Appointments')),
          findsNothing,
        );
      },
    );

    testWidgets(
      'a patient sees no workspace destinations and the screens refuse them',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          size: const Size(420, 900),
          script: (b) => dashboardsFor(b),
        );
        final bar = find.byType(NavigationBar);
        for (final label in ['Dashboard', 'Availability', 'Bookings']) {
          expect(
            find.descendant(of: bar, matching: find.text(label)),
            findsNothing,
            reason: label,
          );
        }
        // a deep link to the workspace is refused in the UI and never calls the backend
        h.container.read(routerProvider).go('/workspace');
        await tester.pumpAndSettle();
        expect(
          find.text('This area is for provider accounts.'),
          findsOneWidget,
        );
        h.container.read(routerProvider).go('/workspace/reservations');
        await tester.pumpAndSettle();
        expect(
          find.text('This area is for provider accounts.'),
          findsOneWidget,
        );
        // the provider screens made no provider-side request at all
        expect(h.backend.count('GET', _doctor), 0);
        expect(h.backend.count('GET', _facility), 0);
        expect(h.backend.count('GET', '/api/v1/reservations/provider'), 0);
      },
    );

    testWidgets(
      'a PROVIDER role without the capability code gets no destinations (UI follows /me permissions)',
      (tester) async {
        await pumpPatientApp(
          tester,
          size: const Size(420, 900),
          account: providerAccountJson(permissions: ['accounts.view_self']),
          script: (b) => dashboardsFor(b),
        );
        expect(
          find.descendant(
            of: find.byType(NavigationBar),
            matching: find.text('Bookings'),
          ),
          findsNothing,
        );
      },
    );

    testWidgets(
      'losing the capability on a /me refresh closes the screen and stops showing data',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/workspace',
          size: _tall,
          account: providerAccountJson(),
          script: (b) => dashboardsFor(b),
        );
        expect(_in('dashboard-profile', 'Dr. Sara Ahmed'), findsOneWidget);
        await switchAccountTo(
          tester,
          h,
          providerAccountJson(permissions: ['accounts.view_self']),
        );
        await tester.pumpAndSettle();
        expect(
          find.text('This area is for provider accounts.'),
          findsOneWidget,
        );
        expect(find.byKey(const Key('dashboard-profile')), findsNothing);
      },
    );
  });

  group('dashboard: Arabic', () {
    testWidgets('renders right-to-left Arabic copy', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/workspace',
        size: _tall,
        language: 'ar',
        account: providerAccountJson(),
        script: (b) => dashboardsFor(b),
      );
      expect(find.text('لوحة التحكم'), findsWidgets);
      expect(_in('dashboard-reservations', 'قيد الانتظار'), findsOneWidget);
      expect(_in('dashboard-profile', 'موثق'), findsOneWidget);
      expect(_in('dashboard-unread', 'الإشعارات'), findsOneWidget);
      expect(
        Directionality.of(
          tester.element(find.byKey(const Key('dashboard-profile'))),
        ),
        TextDirection.rtl,
      );
    });
  });
}
