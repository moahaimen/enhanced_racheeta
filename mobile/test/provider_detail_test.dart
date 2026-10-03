import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/app/router.dart';

import 'support/fake_backend.dart';
import 'support/patient_support.dart';

const _providerPath = '/api/v1/providers/$providerId';
const _tall = Size(800, 1800);

void main() {
  group('provider detail', () {
    testWidgets(
      'shows backend facts and offers booking only for a service with a duration',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/providers/$providerId',
          size: _tall,
          script: (b) => b.on(
            'GET',
            _providerPath,
            (_) => FakeBackend.json(
              200,
              providerJson(
                services: [
                  serviceJson(),
                  serviceJson(id: 'svc-2', title: 'Home visit', duration: null),
                ],
              ),
            ),
          ),
        );
        expect(find.text('Dr. Sara Ahmed'), findsWidgets);
        expect(
          find.text('Cardiologist with ten years of practice.'),
          findsOneWidget,
        );
        expect(find.text('Consultation'), findsOneWidget);
        expect(find.text('Home visit'), findsOneWidget);
        // one Book button: the service without a duration cannot have slots
        expect(find.widgetWithText(FilledButton, 'Book'), findsOneWidget);
      },
    );

    testWidgets(
      'an account without the booking capability sees no Book button',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/providers/$providerId',
          size: _tall,
          account: {
            ...accountJson(),
            'permissions': <String>['accounts.view_self', 'providers.search'],
          },
          script: (b) => b.on(
            'GET',
            _providerPath,
            (_) => FakeBackend.json(200, providerJson()),
          ),
        );
        expect(find.text('Consultation'), findsOneWidget);
        expect(find.widgetWithText(FilledButton, 'Book'), findsNothing);
      },
    );

    testWidgets('Book opens the booking page for that service', (tester) async {
      final h = await pumpPatientApp(
        tester,
        path: '/providers/$providerId',
        size: _tall,
        script: (b) => b
          ..on(
            'GET',
            _providerPath,
            (_) => FakeBackend.json(200, providerJson()),
          )
          ..on(
            'GET',
            '$_providerPath/availability',
            (_) => FakeBackend.json(200, <Object?>[]),
          ),
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Book'));
      await tester.pumpAndSettle();
      expect(
        h.container.read(routerProvider).state.matchedLocation,
        '/providers/$providerId/book/$serviceId',
      );
      expect(find.text('Book an appointment'), findsWidgets);
    });

    testWidgets(
      'a missing provider is the generic not-found text (no existence disclosure)',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/providers/$providerId',
          size: _tall,
          script: (b) => b.on(
            'GET',
            _providerPath,
            (_) => FakeBackend.error(404, 'not_found'),
          ),
        );
        expect(find.text("We couldn't find that."), findsOneWidget);
      },
    );

    testWidgets('a failure offers Try again', (tester) async {
      var fail = true;
      await pumpPatientApp(
        tester,
        path: '/providers/$providerId',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _providerPath,
          (_) => fail
              ? FakeBackend.error(500, 'server_error')
              : FakeBackend.json(200, providerJson()),
        ),
      );
      expect(find.text('Try again'), findsOneWidget);
      fail = false;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Consultation'), findsOneWidget);
    });

    testWidgets('renders Arabic', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/providers/$providerId',
        size: _tall,
        language: 'ar',
        script: (b) => b.on(
          'GET',
          _providerPath,
          (_) => FakeBackend.json(200, providerJson()),
        ),
      );
      expect(find.text('احجز'), findsOneWidget);
      expect(
        Directionality.of(tester.element(find.text('احجز'))),
        TextDirection.rtl,
      );
    });
  });
}
