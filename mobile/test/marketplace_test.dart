import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/app/router.dart';
import 'package:racheeta_mobile/core/paging/paged_notifier.dart';
import 'package:racheeta_mobile/features/marketplace/application/marketplace_providers.dart';
import 'package:racheeta_mobile/shared/search/search_query.dart';

import 'support/domain_support.dart';
import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart' show switchAccountTo;

const _products = '/api/v1/marketplace/products';
const _product = '/api/v1/marketplace/products/$productId';
const _cats = '/api/v1/marketplace/categories';
const _tall = Size(800, 2400);
const _phone = Size(360, 780);

final Map<String, Object?> _prov = browsingProviderJson();

void _categories(FakeBackend b) => b.on(
  'GET',
  _cats,
  (_) => FakeBackend.json(200, [
    categoryJson(),
    categoryJson(id: 'cat-2', ar: 'أجهزة', en: 'Devices'),
  ]),
);

void main() {
  group('navigation and permissions', () {
    testWidgets(
      'a verified-provider account sees the Marketplace entry; patients and companies do not',
      (tester) async {
        await pumpPatientApp(
          tester,
          size: _tall,
          account: _prov,
          script: (_) {},
        );
        expect(find.byKey(const Key('explore-marketplace')), findsOneWidget);
        expect(
          find.byKey(const Key('explore-company-workspace')),
          findsNothing,
        );
      },
    );

    testWidgets(
      'a patient has no entry and a deep link is refused without a request',
      (tester) async {
        final h = await pumpPatientApp(tester, size: _tall, script: (_) {});
        expect(find.byKey(const Key('explore-marketplace')), findsNothing);
        h.container.read(routerProvider).go('/marketplace');
        await tester.pumpAndSettle();
        expect(
          find.text(
            'A verified provider profile is required to browse the marketplace.',
          ),
          findsOneWidget,
        );
        expect(h.backend.count('GET', _products), 0);
      },
    );

    testWidgets(
      'a company sees the company entry and no marketplace browsing',
      (tester) async {
        await pumpPatientApp(
          tester,
          size: _tall,
          account: companyAccountJson(),
          script: (_) {},
        );
        expect(
          find.byKey(const Key('explore-company-workspace')),
          findsOneWidget,
        );
        expect(find.byKey(const Key('explore-marketplace')), findsNothing);
      },
    );
  });

  group('catalogue', () {
    testWidgets(
      'lists targeted products; no search is offered because the API has none',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/marketplace',
          size: _tall,
          account: _prov,
          script: (b) => b.on(
            'GET',
            _products,
            (_) => FakeBackend.json(
              200,
              pageJson([
                productPublicJson(),
                productPublicJson(
                  id: 'p2',
                  title: 'Quote-only device',
                  price: null,
                ),
              ]),
            ),
          ),
        );
        expect(find.text('Digital thermometer'), findsOneWidget);
        expect(find.text('MedTemp · MT-200'), findsNWidgets(2));
        expect(find.text('Diagnostic supplies'), findsWidgets);
        expect(find.text('Al Shifa Supplies'), findsWidgets);
        expect(find.text('25,000 IQD'), findsOneWidget);
        expect(find.text('Price on request'), findsOneWidget);
        expect(find.byKey(const Key('search-field')), findsNothing);
        expect(h.backend.to('GET', _products).single.query, {'page_size': 20});
      },
    );

    testWidgets(
      'the category filter is sent as `category` and restarts at page 1',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/marketplace',
          size: _tall,
          account: _prov,
          script: (b) {
            _categories(b);
            b.on(
              'GET',
              _products,
              (_) => FakeBackend.json(
                200,
                pageJson(
                  [productPublicJson()],
                  count: 40,
                  next: 'https://api.test/x?page=2',
                ),
              ),
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
        await tester.tap(find.byKey(const Key('filters-apply')));
        await tester.pumpAndSettle();
        final query = h.backend.to('GET', _products).last.query;
        expect(query, {'category': 'cat-2', 'page_size': 20});
      },
    );

    testWidgets(
      'pagination, a failing next page, empty state and a safe error',
      (tester) async {
        var fail = true;
        await pumpPatientApp(
          tester,
          path: '/marketplace',
          size: _tall,
          account: _prov,
          script: (b) => b.on('GET', _products, (r) {
            if (r.query['page'] == 2) {
              return fail
                  ? FakeBackend.error(500, 'server_error')
                  : FakeBackend.json(
                      200,
                      pageJson([
                        productPublicJson(id: 'p2', title: 'Second product'),
                      ], count: 2),
                    );
            }
            return FakeBackend.json(
              200,
              pageJson(
                [productPublicJson(title: 'First product')],
                count: 2,
                next: 'https://api.test/x?page=2',
              ),
            );
          }),
        );
        await tester.tap(find.text('Load more'));
        await tester.pumpAndSettle();
        expect(find.text('Could not load more results.'), findsOneWidget);
        expect(find.text('First product'), findsOneWidget);
        fail = false;
        await tester.tap(find.text('Load more'));
        await tester.pumpAndSettle();
        expect(find.text('Second product'), findsOneWidget);
      },
    );

    testWidgets('an empty catalogue explains why', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/marketplace',
        size: _tall,
        account: _prov,
        script: (b) => b.on(
          'GET',
          _products,
          (_) => FakeBackend.json(200, pageJson(<Object?>[])),
        ),
      );
      expect(find.text('No products available'), findsOneWidget);
      expect(
        find.text('Products appear when their category targets your profile.'),
        findsOneWidget,
      );
    });

    testWidgets(
      'a failure is safe; an unverified provider (403) gets the verification message',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/marketplace',
          size: _tall,
          account: _prov,
          script: (b) => b.on(
            'GET',
            _products,
            (_) => FakeBackend.error(
              403,
              'permission_denied',
              message: 'raw backend text',
            ),
          ),
        );
        expect(
          find.text(
            'A verified provider profile is required to browse the marketplace.',
          ),
          findsOneWidget,
        );
        expect(find.textContaining('raw backend text'), findsNothing);
      },
    );

    testWidgets('a server error shows the safe message and retry recovers', (
      tester,
    ) async {
      var fail = true;
      await pumpPatientApp(
        tester,
        path: '/marketplace',
        size: _tall,
        account: _prov,
        script: (b) => b.on(
          'GET',
          _products,
          (_) => fail
              ? FakeBackend.error(500, 'server_error', message: 'Traceback')
              : FakeBackend.json(200, pageJson([productPublicJson()])),
        ),
      );
      expect(find.textContaining('Traceback'), findsNothing);
      fail = false;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Digital thermometer'), findsOneWidget);
    });

    testWidgets(
      'a slow answer for an older filter can never replace the newer results',
      (tester) async {
        final slow = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: '/marketplace',
          size: _tall,
          account: _prov,
          script: (b) => b.on('GET', _products, (r) async {
            if (r.query['category'] == 'old') {
              await slow.future;
              return FakeBackend.json(
                200,
                pageJson([productPublicJson(title: 'OLD RESULT')]),
              );
            }
            return FakeBackend.json(
              200,
              pageJson([productPublicJson(title: 'NEW RESULT')]),
            );
          }),
        );
        final query = h.container.read(productQueryProvider.notifier);
        query.update(const SearchQuery(filters: {'category': 'old'}));
        await tester.pump(const Duration(milliseconds: 50));
        query.update(const SearchQuery(filters: {'category': 'new'}));
        await tester.pump(const Duration(milliseconds: 50));
        slow.complete();
        await tester.pumpAndSettle();
        final state = h.container.read(productsProvider);
        expect(state.phase, PagedPhase.ready);
        expect(state.items.map((p) => p.title), ['NEW RESULT']);
      },
    );

    testWidgets(
      'Arabic right-to-left at phone width with the Arabic category name',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/marketplace',
          size: _phone,
          language: 'ar',
          account: _prov,
          script: (b) => b.on(
            'GET',
            _products,
            (_) => FakeBackend.json(200, pageJson([productPublicJson()])),
          ),
        );
        expect(find.text('مستلزمات التشخيص'), findsOneWidget);
        expect(find.text('السوق الطبي'), findsWidgets);
        expect(
          Directionality.of(tester.element(find.text('مستلزمات التشخيص'))),
          TextDirection.rtl,
        );
        expect(tester.takeException(), isNull);
      },
    );
  });

  group('product detail', () {
    testWidgets(
      'shows the product and the supplier exactly as exposed; the website is text only',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/marketplace/product/$productId',
          size: _tall,
          account: _prov,
          script: (b) => b.on(
            'GET',
            _product,
            (_) => FakeBackend.json(200, productPublicJson()),
          ),
        );
        expect(find.byKey(const Key('product-price')), findsOneWidget);
        expect(find.text('25,000 IQD'), findsOneWidget);
        expect(find.text('MedTemp'), findsOneWidget);
        expect(find.text('Fast contactless reading.'), findsOneWidget);
        expect(find.text('Al Shifa Supplies'), findsOneWidget);
        expect(find.text('+9647700000009'), findsOneWidget);
        expect(find.text('https://shifa.example.test'), findsOneWidget);
        expect(
          find
              .byType(InkWell)
              .evaluate()
              .where((e) => e.widget.key == const Key('open-website')),
          isEmpty,
        );
      },
    );

    testWidgets(
      'a product outside the audience is the generic not-found text',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/marketplace/product/$productId',
          size: _tall,
          account: _prov,
          script: (b) =>
              b.on('GET', _product, (_) => FakeBackend.error(404, 'not_found')),
        );
        expect(find.text("We couldn't find that."), findsOneWidget);
      },
    );
  });

  group('account isolation on the catalogue', () {
    testWidgets('A\'s targeted products and open detail never reach B', (
      tester,
    ) async {
      var who = 'A';
      final gateB = Completer<void>();
      final h = await pumpPatientApp(
        tester,
        path: '/marketplace/product/$productId',
        size: _tall,
        account: _prov,
        script: (b) => b.on('GET', _product, (_) async {
          if (who == 'B') {
            await gateB.future;
            return FakeBackend.error(404, 'not_found');
          }
          return FakeBackend.json(
            200,
            productPublicJson(title: 'PRODUCT TARGETED AT A'),
          );
        }),
      );
      expect(find.text('PRODUCT TARGETED AT A'), findsWidgets);
      who = 'B';
      await switchAccountTo(
        tester,
        h,
        browsingProviderJson(id: otherProviderBrowseId, name: 'Dr B'),
      );
      expect(
        find.text('PRODUCT TARGETED AT A'),
        findsNothing,
        reason: 'while B is loading',
      );
      gateB.complete();
      await tester.pumpAndSettle();
      expect(find.text("We couldn't find that."), findsOneWidget);
    });

    testWidgets('the category filter is reset when the account changes', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/marketplace',
        size: _tall,
        account: _prov,
        script: (b) => b.on(
          'GET',
          _products,
          (_) => FakeBackend.json(200, pageJson([productPublicJson()])),
        ),
      );
      h.container
          .read(productQueryProvider.notifier)
          .update(const SearchQuery(filters: {'category': 'cat-2'}));
      await tester.pumpAndSettle();
      await switchAccountTo(
        tester,
        h,
        browsingProviderJson(id: otherProviderBrowseId, name: 'Dr B'),
      );
      await tester.pumpAndSettle();
      expect(h.container.read(productQueryProvider), const SearchQuery());
    });
  });
}
