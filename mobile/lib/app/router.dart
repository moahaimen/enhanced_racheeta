import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/account/presentation/account_page.dart';
import '../features/auth/application/providers.dart';
import '../features/auth/application/session_state.dart';
import '../features/auth/presentation/login_page.dart';
import '../features/auth/presentation/restoring_page.dart';
import '../features/discovery/presentation/booking_page.dart';
import '../features/discovery/presentation/discovery_page.dart';
import '../features/discovery/presentation/provider_detail_page.dart';
import '../features/home/presentation/home_page.dart';
import '../features/reservations/presentation/reservation_detail_page.dart';
import '../features/reservations/presentation/reservations_page.dart';
import '../features/shell/app_shell.dart';
import '../features/provider/presentation/availability_page.dart';
import '../features/provider/presentation/dashboard_page.dart';
import '../features/provider/presentation/provider_reservation_detail_page.dart';
import '../features/provider/presentation/provider_reservations_page.dart';
import '../features/provider/presentation/slot_form_page.dart';
import '../features/real_estate/presentation/listing_detail_page.dart';
import '../features/real_estate/presentation/owner_listing_detail_page.dart';
import '../features/real_estate/presentation/owner_listings_page.dart';
import '../features/real_estate/presentation/real_estate_page.dart';
import '../features/real_estate/presentation/seller_workspace_page.dart';
import '../shared/widgets/app_scaffold.dart';
import '../shared/widgets/states.dart';

abstract final class AppRoutes {
  static const restoring = '/restoring';
  static const login = '/login';
  static const home = '/';
  static const account = '/account';
  static const providers = '/providers';
  static const reservations = '/reservations';
  static const realEstate = '/real-estate';
  static const seller = '/seller';
  static const workspace = '/workspace';
  static const workspaceAvailability = '/workspace/availability';
  static const workspaceAvailabilityNew = '/workspace/availability/new';
  static const workspaceReservations = '/workspace/reservations';
}

/// Where a given session state is allowed to be. The router is a pure function of the session:
/// signed-out users can only reach the login screen, signed-in users never see it, and the
/// start-up/offline-restore screen is shown until the stored session is resolved.
String? redirectFor(SessionState session, String location) {
  switch (session) {
    case SessionRestoring() || SessionRestoreFailed():
      return location == AppRoutes.restoring ? null : AppRoutes.restoring;
    case SessionAnonymous():
      return location == AppRoutes.login ? null : AppRoutes.login;
    case SessionAuthenticated():
      return (location == AppRoutes.login || location == AppRoutes.restoring)
          ? AppRoutes.home
          : null;
  }
}

final routerProvider = Provider<GoRouter>((ref) {
  // Re-evaluate redirects whenever the session changes.
  final refresh = ValueNotifier<int>(0);
  ref.listen(sessionControllerProvider, (_, _) => refresh.value++);
  ref.onDispose(refresh.dispose);

  final router = GoRouter(
    initialLocation: AppRoutes.restoring,
    refreshListenable: refresh,
    redirect: (context, state) =>
        redirectFor(ref.read(sessionControllerProvider), state.matchedLocation),
    routes: [
      GoRoute(
        path: AppRoutes.restoring,
        builder: (_, _) => const RestoringPage(),
      ),
      GoRoute(path: AppRoutes.login, builder: (_, _) => const LoginPage()),
      ShellRoute(
        builder: (context, state, child) =>
            AppShell(location: state.matchedLocation, child: child),
        routes: [
          GoRoute(path: AppRoutes.home, builder: (_, _) => const HomePage()),
          GoRoute(
            path: AppRoutes.account,
            builder: (_, _) => const AccountPage(),
          ),
          GoRoute(
            path: AppRoutes.providers,
            builder: (_, _) => const DiscoveryPage(),
            routes: [
              GoRoute(
                path: ':id',
                builder: (_, state) =>
                    ProviderDetailPage(providerId: state.pathParameters['id']!),
                routes: [
                  GoRoute(
                    path: 'book/:serviceId',
                    builder: (_, state) => BookingPage(
                      providerId: state.pathParameters['id']!,
                      serviceId: state.pathParameters['serviceId']!,
                    ),
                  ),
                ],
              ),
            ],
          ),
          // 11C provider / facility workspace. Flat routes (not nested) so opening one screen
          // never builds, and fetches for, the others underneath it.
          GoRoute(
            path: AppRoutes.workspace,
            builder: (_, _) => const WorkspacePage(),
          ),
          GoRoute(
            path: AppRoutes.workspaceAvailability,
            builder: (_, _) => const AvailabilityPage(),
          ),
          GoRoute(
            path: AppRoutes.workspaceAvailabilityNew,
            builder: (_, _) => const SlotFormPage(),
          ),
          GoRoute(
            path: AppRoutes.workspaceReservations,
            builder: (_, _) => const ProviderReservationsPage(),
          ),
          GoRoute(
            path: '${AppRoutes.workspaceReservations}/:id',
            builder: (_, state) => ProviderReservationDetailPage(
              reservationId: state.pathParameters['id']!,
            ),
          ),
          // 11D real estate: public catalogue and the property-owner workspace (flat routes).
          GoRoute(
            path: AppRoutes.realEstate,
            builder: (_, _) => const RealEstatePage(),
          ),
          GoRoute(
            path: '${AppRoutes.realEstate}/listing/:id',
            builder: (_, state) =>
                ListingDetailPage(listingId: state.pathParameters['id']!),
          ),
          GoRoute(
            path: AppRoutes.seller,
            builder: (_, _) => const SellerWorkspacePage(),
          ),
          GoRoute(
            path: '${AppRoutes.seller}/listings',
            builder: (_, _) => const OwnerListingsPage(),
          ),
          GoRoute(
            path: '${AppRoutes.seller}/listings/:id',
            builder: (_, state) =>
                OwnerListingDetailPage(listingId: state.pathParameters['id']!),
          ),
          GoRoute(
            path: AppRoutes.reservations,
            builder: (_, _) => const ReservationsPage(),
            routes: [
              GoRoute(
                path: ':id',
                builder: (_, state) => ReservationDetailPage(
                  reservationId: state.pathParameters['id']!,
                ),
              ),
            ],
          ),
        ],
      ),
    ],
    errorBuilder: (context, state) => const AppScaffold(body: EmptyView()),
  );
  ref.onDispose(router.dispose);
  return router;
});
