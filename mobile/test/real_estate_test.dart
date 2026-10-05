import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/core/paging/paged_notifier.dart';
import 'package:racheeta_mobile/features/real_estate/application/real_estate_providers.dart';
import 'package:racheeta_mobile/shared/search/search_query.dart';

import 'support/domain_support.dart';
import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart' show switchAccountTo;

const _list = '/api/v1/real-estate/listings';
const _detail = '/api/v1/real-estate/listings/$listingId';
const _tall = Size(800, 2400);
const _phone = Size(360, 780);

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
    {
      'id': 'g2',
      'slug': 'basra',
      'name_ar': 'البصرة',
      'name_en': 'Basra',
      'country': 'x',
    },
  ]),
);

void main() {
  group('public catalogue', () {
    testWidgets(
      'lists listings with type, transaction, place, price and area',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/real-estate',
          size: _tall,
          script: (b) => b.on(
            'GET',
            _list,
            (_) => FakeBackend.json(
              200,
              pageJson([
                listingJson(),
                listingJson(
                  id: 'l2',
                  title: 'Pharmacy corner',
                  propertyType: 'PHARMACY_LOCATION',
                  transaction: 'RENT',
                  price: null,
                  area: null,
                ),
              ]),
            ),
          ),
        );
        expect(find.text('Clinic floor in Karrada'), findsOneWidget);
        expect(find.text('Clinic · For sale'), findsOneWidget);
        expect(find.textContaining('Karrada'), findsWidgets);
        expect(find.text('150,000,000 IQD'), findsOneWidget);
        expect(find.textContaining('120.5 m²'), findsOneWidget);
        // price on request and a missing area are shown as the backend sent them: no invented values
        expect(find.text('Pharmacy location · For rent'), findsOneWidget);
        expect(find.text('Price on request'), findsOneWidget);
        expect(find.text('2 results'), findsOneWidget);
        final request = h.backend.to('GET', _list).single;
        expect(request.query, {'page_size': 20});
      },
    );

    testWidgets(
      'unknown future codes render as the raw code instead of failing the page',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/real-estate',
          size: _tall,
          script: (b) => b.on(
            'GET',
            _list,
            (_) => FakeBackend.json(
              200,
              pageJson([
                listingJson(
                  propertyType: 'HELIPAD',
                  transaction: 'LEASE_TO_OWN',
                ),
              ]),
            ),
          ),
        );
        expect(find.text('HELIPAD · LEASE_TO_OWN'), findsOneWidget);
      },
    );

    testWidgets(
      'pagination appends the next page and keeps items when a page fails',
      (tester) async {
        var fail = true;
        final h = await pumpPatientApp(
          tester,
          path: '/real-estate',
          size: _tall,
          script: (b) => b.on('GET', _list, (r) {
            if (r.query['page'] == 2) {
              return fail
                  ? FakeBackend.error(500, 'server_error')
                  : FakeBackend.json(
                      200,
                      pageJson([
                        listingJson(id: 'l2', title: 'Second property'),
                      ], count: 2),
                    );
            }
            return FakeBackend.json(
              200,
              pageJson(
                [listingJson(title: 'First property')],
                count: 2,
                next: 'https://api.test/x?page=2',
              ),
            );
          }),
        );
        await tester.tap(find.text('Load more'));
        await tester.pumpAndSettle();
        expect(find.text('Could not load more results.'), findsOneWidget);
        expect(find.text('First property'), findsOneWidget);
        fail = false;
        await tester.tap(find.text('Load more'));
        await tester.pumpAndSettle();
        expect(find.text('Second property'), findsOneWidget);
        expect(find.text('Load more'), findsNothing);
        expect(h.backend.to('GET', _list).map((r) => r.query['page']), [
          null,
          2,
          2,
        ]);
      },
    );

    testWidgets('an empty result is explained and filters can be cleared', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/real-estate',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _list,
          (r) => FakeBackend.json(
            200,
            pageJson(
              r.query.containsKey('transaction_type')
                  ? <Object?>[]
                  : [listingJson()],
            ),
          ),
        ),
      );
      h.container
          .read(listingQueryProvider.notifier)
          .update(const SearchQuery(filters: {'transaction_type': 'RENT'}));
      await tester.pumpAndSettle();
      expect(find.text('No properties found'), findsOneWidget);
      expect(find.text('Try changing your search or filters.'), findsOneWidget);
      await tester.tap(find.text('Clear filters'));
      await tester.pumpAndSettle();
      expect(find.text('Clinic floor in Karrada'), findsOneWidget);
    });

    testWidgets('a failure shows a safe message and Try again recovers', (
      tester,
    ) async {
      var fail = true;
      await pumpPatientApp(
        tester,
        path: '/real-estate',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _list,
          (_) => fail
              ? FakeBackend.error(
                  500,
                  'server_error',
                  message: 'Traceback: db password=secret',
                )
              : FakeBackend.json(200, pageJson([listingJson()])),
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
      expect(find.text('Clinic floor in Karrada'), findsOneWidget);
    });

    testWidgets(
      'search text is debounced, sent as `search`, and restarts at page 1',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/real-estate',
          size: _tall,
          script: (b) => b.on(
            'GET',
            _list,
            (_) => FakeBackend.json(
              200,
              pageJson(
                [listingJson()],
                count: 40,
                next: 'https://api.test/x?page=2',
              ),
            ),
          ),
        );
        await tester.enterText(find.byKey(const Key('search-field')), 'arasat');
        await tester.pump(const Duration(milliseconds: 100));
        expect(h.backend.count('GET', _list), 1, reason: 'still debouncing');
        await tester.pump(const Duration(milliseconds: 500));
        await tester.pumpAndSettle();
        expect(h.backend.to('GET', _list).last.query, {
          'search': 'arasat',
          'page_size': 20,
        });
      },
    );

    testWidgets('filters and ordering are sent as the documented parameters', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/real-estate',
        size: _tall,
        script: (b) {
          _govs(b);
          b.on(
            'GET',
            _list,
            (_) => FakeBackend.json(
              200,
              pageJson(
                [listingJson()],
                count: 40,
                next: 'https://api.test/x?page=2',
              ),
            ),
          );
        },
      );
      await tester.tap(find.byKey(const Key('filters-button')));
      await tester.pumpAndSettle();
      Future<void> pick(String label, String option) async {
        await tester.tap(
          find.widgetWithText(DropdownButtonFormField<String?>, label),
        );
        await tester.pumpAndSettle();
        await tester.tap(find.text(option).last);
        await tester.pumpAndSettle();
      }

      await pick('Transaction', 'For sale');
      await pick('Property type', 'Clinic');
      await pick('Governorate', 'Baghdad');
      await pick('Sort by', 'Price: low to high');
      await tester.tap(find.byKey(const Key('filters-apply')));
      await tester.pumpAndSettle();

      final query = h.backend.to('GET', _list).last.query;
      expect(query, {
        'transaction_type': 'SALE',
        'property_type': 'CLINIC',
        'governorate': 'g1',
        'ordering': 'price',
        'page_size': 20,
      });
      expect(
        query.containsKey('page'),
        isFalse,
        reason: 'a new query restarts at page 1',
      );
      // ordering is not a narrowing filter: the badge counts the other three
      expect(find.text('3'), findsOneWidget);
    });

    testWidgets(
      'a slow answer for an older query can never replace the newer results',
      (tester) async {
        final slow = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: '/real-estate',
          size: _tall,
          script: (b) => b.on('GET', _list, (r) async {
            if (r.query['search'] == 'old') {
              await slow.future;
              return FakeBackend.json(
                200,
                pageJson([listingJson(title: 'OLD RESULT')]),
              );
            }
            return FakeBackend.json(
              200,
              pageJson([listingJson(title: 'NEW RESULT')]),
            );
          }),
        );
        final query = h.container.read(listingQueryProvider.notifier);
        query.update(const SearchQuery(search: 'old'));
        await tester.pump(const Duration(milliseconds: 50));
        query.update(const SearchQuery(search: 'new'));
        await tester.pump(const Duration(milliseconds: 50));
        slow.complete();
        await tester.pumpAndSettle();
        final state = h.container.read(listingsProvider);
        expect(state.phase, PagedPhase.ready);
        expect(state.items.map((l) => l.title), ['NEW RESULT']);
        expect(find.text('OLD RESULT'), findsNothing);
      },
    );

    testWidgets('the search form is reset when the account changes', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/real-estate',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _list,
          (_) => FakeBackend.json(200, pageJson([listingJson()])),
        ),
      );
      h.container
          .read(listingQueryProvider.notifier)
          .update(
            const SearchQuery(
              search: 'private search',
              filters: {'transaction_type': 'RENT'},
            ),
          );
      await tester.pumpAndSettle();
      await switchAccountTo(
        tester,
        h,
        accountJson(
          id: '99999999-9999-4999-8999-999999999999',
          name: 'Patient B',
        ),
      );
      await tester.pumpAndSettle();
      expect(h.container.read(listingQueryProvider), const SearchQuery());
      expect(
        tester
            .widget<TextField>(find.byKey(const Key('search-field')))
            .controller!
            .text,
        isEmpty,
      );
    });

    testWidgets('renders Arabic right-to-left at phone width', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/real-estate',
        size: _phone,
        language: 'ar',
        script: (b) => b.on(
          'GET',
          _list,
          (_) => FakeBackend.json(
            200,
            pageJson([listingJson(), listingJson(id: 'l2', price: null)]),
          ),
        ),
      );
      expect(find.text('عيادة · للبيع'), findsWidgets);
      expect(find.text('السعر عند الطلب'), findsOneWidget);
      expect(find.text('العقارات'), findsWidgets);
      expect(
        Directionality.of(tester.element(find.text('عيادة · للبيع').first)),
        TextDirection.rtl,
      );
      expect(
        tester.takeException(),
        isNull,
        reason: 'no overflow with long Arabic labels',
      );
    });
  });

  group('public detail', () {
    testWidgets(
      'shows the public fields; contact values only as the API exposed them',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/real-estate/listing/$listingId',
          size: _tall,
          script: (b) => b.on(
            'GET',
            _detail,
            (_) => FakeBackend.json(
              200,
              listingJson(phone: '+9647700000001', email: null),
            ),
          ),
        );
        expect(find.text('Clinic floor in Karrada'), findsWidgets);
        expect(find.byKey(const Key('listing-price')), findsOneWidget);
        expect(find.text('150,000,000 IQD'), findsOneWidget);
        expect(find.text('Arasat'), findsOneWidget);
        expect(find.text('Clinic، Medical center'), findsOneWidget);
        expect(find.text('Parking, elevator'), findsOneWidget);
        expect(find.text('Ground floor, street frontage.'), findsOneWidget);
        expect(find.textContaining('Layla Estates'), findsOneWidget);
        expect(find.text('+9647700000001'), findsOneWidget);
        expect(
          find.text('Email'),
          findsNothing,
          reason: 'the email is not public for this contact method',
        );
        // no map, no coordinates
        expect(find.textContaining('33.31'), findsNothing);
      },
    );

    testWidgets(
      'a listing that is not publicly visible is the generic not-found text',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/real-estate/listing/$listingId',
          size: _tall,
          script: (b) =>
              b.on('GET', _detail, (_) => FakeBackend.error(404, 'not_found')),
        );
        expect(find.text("We couldn't find that."), findsOneWidget);
      },
    );

    testWidgets('the Arabic detail is right-to-left', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/real-estate/listing/$listingId',
        size: _phone,
        language: 'ar',
        script: (b) => b.on(
          'GET',
          _detail,
          (_) => FakeBackend.json(
            200,
            listingJson(uses: ['CLINIC', 'FUTURE_USE']),
          ),
        ),
      );
      expect(find.text('المساحة'), findsOneWidget);
      expect(
        find.textContaining('FUTURE_USE'),
        findsOneWidget,
        reason: 'unknown codes stay visible',
      );
      expect(
        Directionality.of(tester.element(find.text('المساحة'))),
        TextDirection.rtl,
      );
    });
  });
}
