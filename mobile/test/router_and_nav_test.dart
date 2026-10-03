import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/app/router.dart';
import 'package:racheeta_mobile/core/api/api_exception.dart';
import 'package:racheeta_mobile/features/auth/application/session_core.dart';
import 'package:racheeta_mobile/features/auth/application/session_state.dart';
import 'package:racheeta_mobile/features/auth/data/auth_models.dart';
import 'package:racheeta_mobile/features/shell/destinations.dart';

import 'support/fake_backend.dart';

Account account({String role = 'PATIENT', List<String>? permissions}) =>
    Account.fromJson({...accountJson(role: role), 'permissions': ?permissions});

void main() {
  group('redirectFor', () {
    final authenticated = SessionAuthenticated(account());
    test('restoring and offline-restore sessions are held on /restoring', () {
      for (final s in [
        const SessionRestoring(),
        SessionRestoreFailed(ApiException.network),
      ]) {
        expect(redirectFor(s, AppRoutes.home), AppRoutes.restoring);
        expect(redirectFor(s, AppRoutes.login), AppRoutes.restoring);
        expect(redirectFor(s, AppRoutes.restoring), isNull);
      }
    });

    test('signed-out users can only reach login', () {
      const s = SessionAnonymous();
      expect(redirectFor(s, AppRoutes.home), AppRoutes.login);
      expect(redirectFor(s, AppRoutes.account), AppRoutes.login);
      expect(redirectFor(s, AppRoutes.restoring), AppRoutes.login);
      expect(redirectFor(s, AppRoutes.login), isNull);
      expect(
        redirectFor(
          const SessionAnonymous(endedBy: SessionEndReason.expired),
          AppRoutes.account,
        ),
        AppRoutes.login,
      );
    });

    test('signed-in users never see login or restoring', () {
      expect(redirectFor(authenticated, AppRoutes.login), AppRoutes.home);
      expect(redirectFor(authenticated, AppRoutes.restoring), AppRoutes.home);
      expect(redirectFor(authenticated, AppRoutes.home), isNull);
      expect(redirectFor(authenticated, AppRoutes.account), isNull);
    });
  });

  group('role-aware destinations (derived from /me)', () {
    final registry = <ShellDestination>[
      ...coreDestinations,
      ShellDestination(
        id: 'provider-only',
        path: '/p',
        icon: Icons.work_outline,
        selectedIcon: Icons.work,
        label: (_) => 'P',
        isAvailableFor: (a) => a.role == AccountRole.provider,
      ),
      ShellDestination(
        id: 'perm',
        path: '/perm',
        icon: Icons.lock_outline,
        selectedIcon: Icons.lock,
        label: (_) => 'Perm',
        isAvailableFor: (a) => a.hasPermission('reservations.create_own'),
      ),
    ];

    test(
      'core destinations are for everyone and nothing unfinished is listed',
      () {
        expect(coreDestinations.map((d) => d.id), ['home', 'account']);
        for (final role in [
          'PATIENT',
          'PROVIDER',
          'MEDICAL_COMPANY',
          'REAL_ESTATE_SELLER',
          'ADMIN',
        ]) {
          expect(destinationsFor(account(role: role)).map((d) => d.id), [
            'home',
            'account',
          ]);
        }
      },
    );

    test('availability follows role and backend permission codes', () {
      expect(destinationsFor(account(), registry: registry).map((d) => d.id), [
        'home',
        'account',
        'perm',
      ]);
      expect(
        destinationsFor(
          account(role: 'PROVIDER', permissions: const []),
          registry: registry,
        ).map((d) => d.id),
        ['home', 'account', 'provider-only'],
      );
    });
  });
}
