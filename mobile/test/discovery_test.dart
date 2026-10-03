import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/app/router.dart';
import 'package:racheeta_mobile/core/paging/paged_notifier.dart';
import 'package:racheeta_mobile/features/auth/application/providers.dart';
import 'package:racheeta_mobile/features/discovery/application/discovery_providers.dart';
import 'package:racheeta_mobile/features/discovery/data/discovery_api.dart';

import 'support/fake_backend.dart';
import 'support/patient_support.dart';

const _providers = '/api/v1/providers';

void reference(FakeBackend b) => b
  ..on(
    'GET',
    '/api/v1/specialties',
    (_) => FakeBackend.json(200, [
      {
        'id': 's1',
        'slug': 'cardiology',
        'name_ar': 'أمراض القلب',
        'name_en': 'Cardiology',
        'parent': null,
      },
    ]),
  )
  ..on(
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
      {
        'id': 'g2',
        'slug': 'basra',
        'name_ar': 'البصرة',
        'name_en': 'Basra',
        'country': 'x',
      },
    ]),
  )
  ..on(
    'GET',
    '/api/v1/geo/cities',
    (r) => FakeBackend.json(200, [
      {
        'id': 'c1',
        'slug': 'karrada',
        'name_ar': 'الكرادة',
        'name_en': 'Karrada',
        'governorate': r.query['governorate'],
      },
    ]),
  );

void main() {
  group('DiscoveryFilters', () {
    test('map to exactly the documented query parameters', () {
      const filters = DiscoveryFilters(
        search: '  sara ',
        kind: 'PRACTITIONER',
        type: 'DOCTOR',
        specialtySlug: 'cardiology',
        governorateId: 'g1',
        cityId: 'c1',
        ordering: DiscoveryOrdering.newest,
      );
      expect(filters.toQuery(), {
        'search': 'sara',
        'kind': 'PRACTITIONER',
        'type': 'DOCTOR',
        'specialty': 'cardiology',
        'governorate': 'g1',
        'city': 'c1',
        'ordering': '-created_at',
      });
      expect(const DiscoveryFilters().toQuery(), isEmpty);
      expect(filters.activeFilterCount, 5);
    });

    test(
      'changing the governorate drops the city that belonged to the old one',
      () {
        const filters = DiscoveryFilters(governorateId: 'g1', cityId: 'c1');
        expect(filters.copyWith(governorateId: 'g2').cityId, isNull);
        expect(filters.copyWith(type: 'NURSE').cityId, 'c1');
        expect(filters.copyWith(governorateId: null).governorateId, isNull);
      },
    );
  });

  group('discovery screen', () {
    testWidgets('lists backend providers with only backend facts', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/providers',
        script: (b) => b
          ..on(
            'GET',
            _providers,
            (_) => FakeBackend.json(
              200,
              pageJson([
                cardJson(),
                cardJson(
                  id: 'p2',
                  name: 'Al Noor Clinic',
                  type: 'MEDICAL_CENTER',
                  kind: 'FACILITY',
                  rating: null,
                  reviews: 0,
                ),
              ]),
            ),
          )
          ..on(
            'GET',
            '/api/v1/specialties',
            (_) => FakeBackend.json(200, <Object?>[]),
          ),
      );
      expect(find.text('Dr. Sara Ahmed'), findsOneWidget);
      expect(find.text('Al Noor Clinic'), findsOneWidget);
      expect(find.text('2 results'), findsOneWidget);
      expect(find.textContaining('Cardiology'), findsWidgets);
      expect(find.textContaining('Karrada'), findsWidgets);
      expect(find.text('Doctor'), findsOneWidget);
      expect(find.text('Medical center'), findsOneWidget);
      // rating exactly as reported; a provider without reviews says so, never a fabricated rating
      expect(find.text('4.5 · 12 reviews'), findsOneWidget);
      expect(find.text('No reviews yet'), findsOneWidget);
    });

    testWidgets('shows loading, then results; an empty result is explained', (
      tester,
    ) async {
      final gate = Completer<void>();
      await tester.runAsync(() async {});
      final h = await pumpPatientApp(tester, script: (b) {});
      h.backend.on('GET', _providers, (_) async {
        await gate.future;
        return FakeBackend.json(200, pageJson(<Object?>[]));
      });
      h.container.read(routerProvider).go('/providers');
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      gate.complete();
      await tester.pumpAndSettle();
      expect(find.text('No providers found'), findsOneWidget);
      expect(find.text('Try changing your search or filters.'), findsOneWidget);
      expect(find.text('Clear filters'), findsNothing); // nothing to clear
    });

    testWidgets('failure shows a safe message and Try again recovers', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/providers',
        script: (b) => b.on(
          'GET',
          _providers,
          (_) => FakeBackend.error(
            500,
            'server_error',
            message: 'Traceback: db password=secret',
          ),
        ),
      );
      expect(
        find.text('Something went wrong on our side. Try again later.'),
        findsOneWidget,
      );
      expect(find.textContaining('Traceback'), findsNothing);
      expect(find.textContaining('secret'), findsNothing);

      h.backend.on(
        'GET',
        _providers,
        (_) => FakeBackend.json(200, pageJson([cardJson()])),
      );
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Dr. Sara Ahmed'), findsOneWidget);
    });

    testWidgets('network failure maps to the offline message', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/providers',
        script: (b) => b.on('GET', _providers, FakeBackend.networkDown),
      );
      expect(find.textContaining('Could not reach the server'), findsOneWidget);
    });

    testWidgets('pagination appends the next page and stops at the last', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/providers',
        script: (b) => b.on('GET', _providers, (r) {
          if (r.query['page'] == 2) {
            return FakeBackend.json(
              200,
              pageJson([cardJson(id: 'p3', name: 'Third Provider')], count: 3),
            );
          }
          return FakeBackend.json(
            200,
            pageJson(
              [cardJson(), cardJson(id: 'p2', name: 'Second Provider')],
              count: 3,
              next: 'https://api.test/api/v1/providers?page=2',
            ),
          );
        }),
      );
      expect(find.text('Third Provider'), findsNothing);
      await tester.scrollUntilVisible(
        find.text('Load more'),
        200,
        scrollable: find.byType(Scrollable).last,
      );
      await tester.tap(find.text('Load more'));
      await tester.pumpAndSettle();
      expect(find.text('Third Provider'), findsOneWidget);
      expect(find.text('Dr. Sara Ahmed'), findsOneWidget);
      expect(find.text('Load more'), findsNothing);
      expect(h.backend.to('GET', _providers).map((r) => r.query['page']), [
        null,
        2,
      ]);
    });

    testWidgets(
      'a failing next page keeps the loaded items and can be retried',
      (tester) async {
        var fail = true;
        await pumpPatientApp(
          tester,
          path: '/providers',
          script: (b) => b.on('GET', _providers, (r) {
            if (r.query['page'] == 2) {
              if (fail) return FakeBackend.error(500, 'server_error');
              return FakeBackend.json(
                200,
                pageJson([
                  cardJson(id: 'p3', name: 'Third Provider'),
                ], count: 3),
              );
            }
            return FakeBackend.json(
              200,
              pageJson(
                [cardJson()],
                count: 3,
                next: 'https://api.test/api/v1/providers?page=2',
              ),
            );
          }),
        );
        await tester.scrollUntilVisible(
          find.text('Load more'),
          200,
          scrollable: find.byType(Scrollable).last,
        );
        await tester.tap(find.text('Load more'));
        await tester.pumpAndSettle();
        expect(find.text('Could not load more results.'), findsOneWidget);
        expect(find.text('Dr. Sara Ahmed'), findsOneWidget);
        fail = false;
        await tester.tap(find.text('Load more'));
        await tester.pumpAndSettle();
        expect(find.text('Third Provider'), findsOneWidget);
      },
    );

    testWidgets(
      'search text and filters are sent together and restart pagination',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/providers',
          script: (b) {
            reference(b);
            b.on(
              'GET',
              _providers,
              (r) => FakeBackend.json(
                200,
                pageJson(
                  [cardJson()],
                  count: 40,
                  next: 'https://api.test/x?page=2',
                ),
              ),
            );
          },
        );
        // search (debounced)
        await tester.enterText(find.byType(TextField).first, 'sara');
        await tester.pump(const Duration(milliseconds: 500));
        await tester.pumpAndSettle();
        expect(h.backend.to('GET', _providers).last.query, {
          'search': 'sara',
          'page_size': 20,
        });

        // filter sheet: kind + governorate (+ city appears)
        await tester.tap(find.byTooltip('Filters'));
        await tester.pumpAndSettle();
        await tester.tap(
          find.widgetWithText(
            DropdownButtonFormField<String?>,
            'Provider kind',
          ),
        );
        await tester.pumpAndSettle();
        await tester.tap(find.text('Facility').last);
        await tester.pumpAndSettle();
        await tester.tap(
          find.widgetWithText(DropdownButtonFormField<String?>, 'Governorate'),
        );
        await tester.pumpAndSettle();
        await tester.tap(find.text('Baghdad').last);
        await tester.pumpAndSettle();
        expect(find.text('City'), findsOneWidget);
        await tester.tap(find.text('Apply'));
        await tester.pumpAndSettle();

        final query = h.backend.to('GET', _providers).last.query;
        expect(query, {
          'search': 'sara',
          'kind': 'FACILITY',
          'governorate': 'g1',
          'page_size': 20,
        });
        expect(
          query.containsKey('page'),
          isFalse,
          reason: 'a new query restarts at page 1',
        );
        expect(
          find.text('2'),
          findsOneWidget,
        ); // filter badge: kind + governorate
      },
    );

    testWidgets('empty results with active filters offer to clear them', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/providers',
        script: (b) => b.on(
          'GET',
          _providers,
          (r) => FakeBackend.json(
            200,
            pageJson(r.query.containsKey('type') ? <Object?>[] : [cardJson()]),
          ),
        ),
      );
      h.container
          .read(discoveryFiltersProvider.notifier)
          .update(const DiscoveryFilters(type: 'PHARMACY'));
      await tester.pumpAndSettle();
      expect(find.text('No providers found'), findsOneWidget);
      await tester.tap(find.text('Clear filters'));
      await tester.pumpAndSettle();
      expect(find.text('Dr. Sara Ahmed'), findsOneWidget);
    });
  });

  group('stale responses', () {
    testWidgets(
      'a slow answer for an older search can never replace newer results',
      (tester) async {
        final slow = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          script: (b) => b.on('GET', _providers, (r) async {
            if (r.query['search'] == 'old') {
              await slow.future;
              return FakeBackend.json(
                200,
                pageJson([cardJson(name: 'OLD RESULT')]),
              );
            }
            return FakeBackend.json(
              200,
              pageJson([cardJson(name: 'NEW RESULT')]),
            );
          }),
        );
        final filters = h.container.read(discoveryFiltersProvider.notifier);
        h.container.listen(providerSearchProvider, (_, _) {});
        filters.update(const DiscoveryFilters(search: 'old'));
        await tester.pump(const Duration(milliseconds: 50));
        filters.update(const DiscoveryFilters(search: 'new'));
        await tester.pump(const Duration(milliseconds: 50));
        slow.complete();
        await tester.pump(const Duration(milliseconds: 50));
        final state = h.container.read(providerSearchProvider);
        expect(state.phase, PagedPhase.ready);
        expect(state.items.map((c) => c.displayName), ['NEW RESULT']);
      },
    );

    testWidgets(
      'a late page-2 of an old query is not appended to the new query',
      (tester) async {
        final slowPage2 = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          script: (b) => b.on('GET', _providers, (r) async {
            if (r.query['page'] == 2) {
              await slowPage2.future;
              return FakeBackend.json(
                200,
                pageJson([cardJson(id: 'late', name: 'LATE PAGE 2')], count: 2),
              );
            }
            final tag = r.query['search'] == 'b' ? 'B-1' : 'A-1';
            return FakeBackend.json(
              200,
              pageJson(
                [cardJson(id: tag, name: tag)],
                count: 2,
                next: 'https://api.test/x?page=2',
              ),
            );
          }),
        );
        final filters = h.container.read(discoveryFiltersProvider.notifier);
        h.container.listen(providerSearchProvider, (_, _) {});
        filters.update(const DiscoveryFilters(search: 'a'));
        await tester.pumpAndSettle();
        final loading = h.container
            .read(providerSearchProvider.notifier)
            .loadMore();
        await tester.pump(const Duration(milliseconds: 20));
        filters.update(const DiscoveryFilters(search: 'b'));
        await tester.pumpAndSettle();
        slowPage2.complete();
        await loading;
        await tester.pumpAndSettle();
        expect(
          h.container
              .read(providerSearchProvider)
              .items
              .map((c) => c.displayName),
          ['B-1'],
        );
      },
    );

    testWidgets(
      'logout and a different login reset search state and drop late answers',
      (tester) async {
        final slow = Completer<void>();
        var account = 'A';
        final h = await pumpPatientApp(
          tester,
          script: (b) => b
            ..on('GET', _providers, (r) async {
              if (account == 'A') {
                await slow.future;
                return FakeBackend.json(
                  200,
                  pageJson([cardJson(name: 'ACCOUNT A DATA')]),
                );
              }
              return FakeBackend.json(
                200,
                pageJson([cardJson(name: 'ACCOUNT B DATA')]),
              );
            })
            ..on('POST', '/api/v1/auth/logout', (_) => FakeBackend.noContent())
            ..on(
              'POST',
              '/api/v1/auth/login',
              (_) => FakeBackend.json(200, tokens('ab', 'rb')),
            ),
        );
        h.container.read(routerProvider).go('/providers');
        await tester.pump(const Duration(milliseconds: 50));
        h.container
            .read(discoveryFiltersProvider.notifier)
            .update(const DiscoveryFilters(search: 'private query'));
        await tester.pump(const Duration(milliseconds: 50));
        await h.container.read(sessionControllerProvider.notifier).logout();
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
        await h.container
            .read(sessionControllerProvider.notifier)
            .login(email: 'b@example.com', password: 'pw');
        slow.complete();
        await tester.pumpAndSettle();
        h.container.read(routerProvider).go('/providers');
        await tester.pumpAndSettle();
        expect(find.text('ACCOUNT A DATA'), findsNothing);
        expect(find.text('ACCOUNT B DATA'), findsOneWidget);
        expect(
          h.container.read(discoveryFiltersProvider).search,
          isEmpty,
          reason: "previous account's search text is gone",
        );
      },
    );
  });
}
