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

/// A patient reservation, keyed by (account, id). The account is part of the key so that when the
/// signed-in account changes the new account starts from a loading state instead of seeing the
/// previous account's reservation while its own request is in flight.
typedef ReservationDetailKey = ({String? account, String id});

final reservationDetailProvider = FutureProvider.autoDispose
    .family<Reservation, ReservationDetailKey>((ref, key) {
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      return ref
          .watch(reservationsApiProvider)
          .detail(key.id, cancelToken: token);
    }, retry: noRetry);
