import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/page.dart';
import '../../../core/paging/paged_notifier.dart';
import '../../auth/application/account_scope.dart';
import '../../auth/application/providers.dart';
import '../data/reservation_models.dart';
import '../data/reservations_api.dart';

final Provider<ReservationsApi> reservationsApiProvider =
    Provider<ReservationsApi>(
      (ref) => ReservationsApi(ref.watch(apiClientProvider)),
    );

/// The signed-in patient's reservations. Rebuilt on account change, so another account's list is
/// never shown; invalidated after a booking or cancellation.
class ReservationListController extends PagedNotifier<Reservation> {
  @override
  PagedState<Reservation> build() {
    ref.watch(accountIdProvider);
    return start();
  }

  @override
  Future<Page<Reservation>> fetchPage(int page, CancelToken token) => ref
      .read(reservationsApiProvider)
      .list(page: page, pageSize: PagedNotifier.pageSize, cancelToken: token);
}

final reservationListProvider =
    NotifierProvider<ReservationListController, PagedState<Reservation>>(
      ReservationListController.new,
      retry: noRetry,
    );

final reservationDetailProvider = FutureProvider.autoDispose
    .family<Reservation, String>((ref, id) {
      ref.watch(accountIdProvider);
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      return ref.watch(reservationsApiProvider).detail(id, cancelToken: token);
    }, retry: noRetry);
