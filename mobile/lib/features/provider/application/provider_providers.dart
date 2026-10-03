import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/page.dart';
import '../../../core/paging/paged_notifier.dart';
import '../../auth/application/account_scope.dart';
import '../../auth/application/providers.dart';
import '../../auth/application/session_state.dart';
import '../data/provider_api.dart';
import '../provider_capability.dart';
import '../data/provider_models.dart';

final Provider<ProviderApi> providerApiProvider = Provider<ProviderApi>(
  (ref) => ProviderApi(ref.watch(apiClientProvider)),
);

/// Whether the signed-in account may use the provider workspace, from the live `/me` data (so it
/// follows permission changes, logout and account switching).
final Provider<bool> canUseProviderWorkspaceProvider = Provider<bool>((ref) {
  final session = ref.watch(sessionControllerProvider);
  return session is SessionAuthenticated &&
      session.account.hasPermission(providerCapability);
});

/// A record id scoped to the signed-in account. Families keyed by this never hand one account's
/// cached value to another: when the account changes, the key changes, so the new account starts
/// from a loading state instead of seeing the previous account's data while it reloads.
typedef AccountScoped<T> = ({String? account, T value});

/// The dashboard to show, decided by the server (`GET /dashboards/`): `null` when the account has
/// no provider dashboard (for example no provider profile yet).
final providerDashboardProvider = FutureProvider.autoDispose
    .family<ProviderDashboard?, String?>((ref, accountId) async {
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      final api = ref.watch(providerApiProvider);
      final index = await api.dashboardIndex(cancelToken: token);
      final kind = index.providerKind;
      if (kind == null) return null;
      return api.dashboard(kind, cancelToken: token);
    }, retry: noRetry);

/// The caller's own services (for choosing what a new time slot is for).
final ownServicesProvider = FutureProvider.autoDispose
    .family<List<OwnService>, String?>((ref, accountId) {
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      return ref.watch(providerApiProvider).services(cancelToken: token);
    }, retry: noRetry);

/// The caller's availability slots. Rebuilt on account change (so another account's slots are
/// never shown) and invalidated after a creation or removal.
class ProviderSlotsController extends PagedNotifier<ProviderSlot> {
  @override
  PagedState<ProviderSlot> build() {
    ref.watch(accountIdProvider);
    return start();
  }

  @override
  Future<Page<ProviderSlot>> fetchPage(int page, CancelToken token) =>
      ref.read(providerApiProvider).slots(page: page, cancelToken: token);
}

final providerSlotsProvider =
    NotifierProvider<ProviderSlotsController, PagedState<ProviderSlot>>(
      ProviderSlotsController.new,
      retry: noRetry,
    );

/// Reservations received by the caller's provider profile, in the backend's order.
class ProviderReservationListController
    extends PagedNotifier<ProviderReservation> {
  @override
  PagedState<ProviderReservation> build() {
    ref.watch(accountIdProvider);
    return start();
  }

  @override
  Future<Page<ProviderReservation>> fetchPage(int page, CancelToken token) =>
      ref
          .read(providerApiProvider)
          .reservations(
            page: page,
            pageSize: PagedNotifier.pageSize,
            cancelToken: token,
          );
}

final providerReservationListProvider =
    NotifierProvider<
      ProviderReservationListController,
      PagedState<ProviderReservation>
    >(ProviderReservationListController.new, retry: noRetry);

final providerReservationDetailProvider = FutureProvider.autoDispose
    .family<ProviderReservation, AccountScoped<String>>((ref, key) {
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      return ref
          .watch(providerApiProvider)
          .reservation(key.value, cancelToken: token);
    }, retry: noRetry);
