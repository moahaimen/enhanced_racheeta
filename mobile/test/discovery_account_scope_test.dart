import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/features/discovery/application/discovery_providers.dart';

import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart' show switchAccountTo;

/// Provider discovery (Phase 11B) must not carry account A's typed search or an open filter draft
/// into account B when `/me` changes on the mounted route.
const _providers = '/api/v1/providers';
const _tall = Size(800, 2400);

final Map<String, Object?> _b = accountJson(
  id: '99999999-9999-4999-8999-999999999999',
  name: 'Patient B',
);

void _script(FakeBackend b) {
  b.on('GET', _providers, (_) => FakeBackend.json(200, pageJson([cardJson()])));
  b.on('GET', '/api/v1/specialties', (_) => FakeBackend.json(200, <Object?>[]));
  b.on(
    'GET',
    '/api/v1/geo/governorates',
    (_) => FakeBackend.json(200, <Object?>[]),
  );
}

void main() {
  testWidgets(
    'a pending search debounce of A is dropped and never sent for B',
    (tester) async {
      final h = await pumpPatientApp(
        tester,
        path: '/providers',
        size: _tall,
        script: _script,
      );
      await tester.enterText(find.byType(TextField), 'secret-A');
      await tester.pump(const Duration(milliseconds: 100));
      await switchAccountTo(tester, h, _b);
      await tester.pump(const Duration(milliseconds: 700));
      await tester.pumpAndSettle();
      expect(h.container.read(discoveryFiltersProvider).search, isEmpty);
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.text,
        isEmpty,
      );
      for (final request in h.backend.to('GET', _providers)) {
        expect(request.query.containsKey('search'), isFalse);
      }
    },
  );

  testWidgets('without an account change the debounce still applies', (
    tester,
  ) async {
    final h = await pumpPatientApp(
      tester,
      path: '/providers',
      size: _tall,
      script: _script,
    );
    await tester.enterText(find.byType(TextField), 'cardio');
    await tester.pump(const Duration(milliseconds: 600));
    await tester.pumpAndSettle();
    expect(h.backend.to('GET', _providers).last.query['search'], 'cardio');
  });

  testWidgets('A\'s unapplied filter draft is never applied to B', (
    tester,
  ) async {
    final h = await pumpPatientApp(
      tester,
      path: '/providers',
      size: _tall,
      script: _script,
    );
    await tester.tap(find.byTooltip('Filters'));
    await tester.pumpAndSettle();
    await tester.tap(
      find.widgetWithText(DropdownButtonFormField<String?>, 'Provider kind'),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Facility').last);
    await tester.pumpAndSettle();
    await switchAccountTo(tester, h, _b);
    await tester.pumpAndSettle();
    // finish A's sheet now that B is signed in
    if (find.text('Apply').evaluate().isNotEmpty) {
      await tester.tap(find.text('Apply'));
      await tester.pumpAndSettle();
    }
    expect(h.container.read(discoveryFiltersProvider).activeFilterCount, 0);
    for (final request in h.backend.to('GET', _providers)) {
      expect(request.query.containsKey('kind'), isFalse);
    }
  });
}
