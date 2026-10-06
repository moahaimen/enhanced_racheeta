import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/features/jobs/application/jobs_providers.dart';
import 'package:racheeta_mobile/features/marketplace/application/marketplace_providers.dart';
import 'package:racheeta_mobile/features/real_estate/application/real_estate_providers.dart';
import 'package:racheeta_mobile/shared/search/search_query.dart';

import 'support/domain_support.dart';
import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart' show switchAccountTo;

/// A search/filter value created under account A must never become account B's query when `/me`
/// changes while the same route (and the same `SearchFilterBar`) stays mounted.
const _jobs = '/api/v1/jobs';
const _estate = '/api/v1/real-estate/listings';
const _products = '/api/v1/marketplace/products';
const _tall = Size(800, 2400);

final Map<String, Object?> _b = accountJson(
  id: '99999999-9999-4999-8999-999999999999',
  name: 'Patient B',
);

void _govs(FakeBackend b) => b.on(
  'GET',
  '/api/v1/geo/governorates',
  (_) => FakeBackend.json(200, [
    {
      'id': 'g1',
      'slug': 'baghdad',
      'name_ar': 'بغداد',
      'name_en': 'Baghdad',
      'country': 'x',
    },
  ]),
);

String _boxText(WidgetTester tester) => tester
    .widget<TextField>(find.byKey(const Key('search-field')))
    .controller!
    .text;

void main() {
  group('pending debounce', () {
    testWidgets('Jobs: A\'s typed text is dropped, never sent for B', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/jobs',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _jobs,
          (_) => FakeBackend.json(200, pageJson([jobCardJson()])),
        ),
      );
      await tester.enterText(find.byKey(const Key('search-field')), 'secret-A');
      await tester.pump(const Duration(milliseconds: 100));
      expect(h.backend.count('GET', _jobs), 1, reason: 'still debouncing');
      await switchAccountTo(tester, h, _b);
      await tester.pump(const Duration(milliseconds: 700));
      await tester.pumpAndSettle();
      expect(h.container.read(jobQueryProvider), const SearchQuery());
      expect(_boxText(tester), isEmpty);
      expect(find.text('secret-A'), findsNothing);
      for (final request in h.backend.to('GET', _jobs)) {
        expect(request.query.containsKey('q'), isFalse);
      }
    });

    testWidgets('Real estate: A\'s typed text is dropped, never sent for B', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/real-estate',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _estate,
          (_) => FakeBackend.json(200, pageJson([listingJson()])),
        ),
      );
      await tester.enterText(find.byKey(const Key('search-field')), 'secret-A');
      await tester.pump(const Duration(milliseconds: 100));
      await switchAccountTo(tester, h, _b);
      await tester.pump(const Duration(milliseconds: 700));
      await tester.pumpAndSettle();
      expect(h.container.read(listingQueryProvider), const SearchQuery());
      expect(_boxText(tester), isEmpty);
      for (final request in h.backend.to('GET', _estate)) {
        expect(request.query.containsKey('search'), isFalse);
      }
    });

    testWidgets('without an account change the debounce still applies', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/jobs',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _jobs,
          (_) => FakeBackend.json(200, pageJson([jobCardJson()])),
        ),
      );
      await tester.enterText(find.byKey(const Key('search-field')), 'icu');
      await tester.pump(const Duration(milliseconds: 600));
      await tester.pumpAndSettle();
      expect(h.backend.to('GET', _jobs).last.query['q'], 'icu');
    });
  });

  group('open filter sheet', () {
    Future<void> pickProfession(WidgetTester tester) async {
      await tester.tap(find.byKey(const Key('filters-button')));
      await tester.pumpAndSettle();
      await tester.tap(
        find.widgetWithText(DropdownButtonFormField<String?>, 'Profession'),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Nurse').last);
      await tester.pumpAndSettle();
    }

    testWidgets('Jobs: A\'s unapplied draft is never applied to B', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/jobs',
        size: _tall,
        script: (b) {
          _govs(b);
          b.on(
            'GET',
            _jobs,
            (_) => FakeBackend.json(200, pageJson([jobCardJson()])),
          );
        },
      );
      await pickProfession(tester);
      await switchAccountTo(tester, h, _b);
      await tester.pumpAndSettle();
      // Finish the old sheet if it is somehow still there.
      if (find.byKey(const Key('filters-apply')).evaluate().isNotEmpty) {
        await tester.tap(find.byKey(const Key('filters-apply')));
        await tester.pumpAndSettle();
      }
      expect(h.container.read(jobQueryProvider), const SearchQuery());
      expect(find.byKey(const Key('filters-apply')), findsNothing);
      for (final request in h.backend.to('GET', _jobs)) {
        expect(request.query.containsKey('profession'), isFalse);
      }
      // the route itself was not popped
      expect(find.text('Jobs'), findsWidgets);
    });

    testWidgets('Jobs: B can still filter normally afterwards', (tester) async {
      final h = await pumpPatientApp(
        tester,
        path: '/jobs',
        size: _tall,
        script: (b) {
          _govs(b);
          b.on(
            'GET',
            _jobs,
            (_) => FakeBackend.json(200, pageJson([jobCardJson()])),
          );
        },
      );
      await pickProfession(tester);
      await switchAccountTo(tester, h, _b);
      await tester.pumpAndSettle();
      await pickProfession(tester);
      await tester.tap(find.byKey(const Key('filters-apply')));
      await tester.pumpAndSettle();
      expect(h.container.read(jobQueryProvider).filters, {
        'profession': 'NURSE',
      });
    });

    testWidgets('Marketplace: A\'s category draft is never applied to B', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/marketplace',
        size: _tall,
        account: browsingProviderJson(),
        script: (b) {
          b.on(
            'GET',
            '/api/v1/marketplace/categories',
            (_) => FakeBackend.json(200, [
              categoryJson(),
              categoryJson(id: 'cat-2', ar: 'أجهزة', en: 'Devices'),
            ]),
          );
          b.on(
            'GET',
            _products,
            (_) => FakeBackend.json(200, pageJson([productPublicJson()])),
          );
        },
      );
      await tester.tap(find.byKey(const Key('filters-button')));
      await tester.pumpAndSettle();
      await tester.tap(
        find.widgetWithText(DropdownButtonFormField<String?>, 'Category'),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Devices').last);
      await tester.pumpAndSettle();
      await switchAccountTo(
        tester,
        h,
        browsingProviderJson(id: otherProviderBrowseId, name: 'Dr B'),
      );
      await tester.pumpAndSettle();
      if (find.byKey(const Key('filters-apply')).evaluate().isNotEmpty) {
        await tester.tap(find.byKey(const Key('filters-apply')));
        await tester.pumpAndSettle();
      }
      expect(h.container.read(productQueryProvider), const SearchQuery());
      for (final request in h.backend.to('GET', _products)) {
        expect(request.query.containsKey('category'), isFalse);
      }
    });
  });
}
