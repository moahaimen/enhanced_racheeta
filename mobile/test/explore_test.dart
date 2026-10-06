import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/features/auth/data/auth_models.dart';
import 'package:racheeta_mobile/features/explore/explore_entries.dart';

import 'support/domain_support.dart';
import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart' show switchAccountTo;

Set<String> _ids(Map<String, Object?> account, Set<String> dashboards) =>
    exploreFor(Account.fromJson(account), dashboards).map((e) => e.id).toSet();

void main() {
  group('Explore entries by role', () {
    test('a patient sees only the public areas', () {
      expect(_ids(accountJson(), {'patient'}), {'jobs', 'real-estate'});
    });

    test(
      'a verified provider (marketplace capability) also gets the marketplace',
      () {
        final provider = browsingProviderJson();
        expect(_ids(provider, {'doctor'}), {
          'jobs',
          'real-estate',
          'marketplace',
        });
      },
    );

    test('a company account gets its workspace, a seller gets the seller workspace', () {
      expect(
        _ids(companyAccountJson(), {'medical_company'}),
        contains('company-workspace'),
      );
      expect(
        _ids(sellerAccountJson(), {'real_estate_owner'}),
        contains('seller-workspace'),
      );
      expect(
        _ids(companyAccountJson(), {'medical_company'}),
        isNot(contains('seller-workspace')),
      );
      expect(
        _ids(sellerAccountJson(), {'real_estate_owner'}),
        isNot(contains('company-workspace')),
      );
    });

    test('the recruiter entry follows the server dashboard index, not a role or capability', () {
      expect(
        _ids(recruiterAccountJson(), {'doctor'}),
        isNot(contains('recruiter-workspace')),
      );
      expect(
        _ids(recruiterAccountJson(), {'doctor', 'recruiter'}),
        contains('recruiter-workspace'),
      );
      // a patient the server lists as a recruiter gets the entry too: membership decides
      expect(
        _ids(accountJson(), {'patient', 'recruiter'}),
        contains('recruiter-workspace'),
      );
    });

    test('no entry opens an external address', () {
      for (final entry in exploreEntries) {
        expect(entry.path, startsWith('/'), reason: entry.id);
        expect(entry.path, isNot(contains('://')), reason: entry.id);
      }
    });
  });

  testWidgets(
    'the recruiter entry of A is gone for B on the same Home screen',
    (tester) async {
      var who = 'A';
      final h = await pumpPatientApp(
        tester,
        size: const Size(800, 2400),
        account: recruiterAccountJson(name: 'Recruiter A'),
        script: (b) => b.on(
          'GET',
          '/api/v1/dashboards/',
          (_) => FakeBackend.json(200, {
            'dashboards': who == 'A' ? ['doctor', 'recruiter'] : ['patient'],
          }),
        ),
      );
      expect(
        find.byKey(const Key('explore-recruiter-workspace')),
        findsOneWidget,
      );
      who = 'B';
      await switchAccountTo(
        tester,
        h,
        accountJson(
          id: '99999999-9999-4999-8999-999999999999',
          name: 'Patient B',
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('explore-recruiter-workspace')),
        findsNothing,
      );
      expect(find.byKey(const Key('explore-jobs')), findsOneWidget);
    },
  );
}
