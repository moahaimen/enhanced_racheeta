import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/error_messages.dart';
import '../../../core/paging/paged_notifier.dart';
import '../../../core/time/time_providers.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/format/labels.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/states.dart';
import '../application/reservation_providers.dart';
import '../data/reservation_models.dart';

/// The patient's reservations, newest appointment first as the backend orders them. The two
/// headings ("Upcoming" / "Past and closed") are a presentation grouping of the loaded items.
class ReservationsPage extends ConsumerWidget {
  const ReservationsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final state = ref.watch(reservationListProvider);
    final controller = ref.read(reservationListProvider.notifier);

    Widget body;
    switch (state.phase) {
      case PagedPhase.loading:
        body = const LoadingView();
      case PagedPhase.error:
        body = ErrorView(
          message: apiErrorMessage(l10n, state.error!),
          onRetry: () async => controller.reload(),
        );
      case PagedPhase.ready:
        body = state.items.isEmpty
            ? _Empty()
            : _List(state: state, onLoadMore: controller.loadMore);
    }
    return AppScaffold(
      title: l10n.reservationsTitle,
      scrollable: false,
      body: state.phase == PagedPhase.ready && state.items.isNotEmpty
          ? RefreshIndicator(
              onRefresh: () async => controller.reload(),
              child: body,
            )
          : body,
    );
  }
}

class _Empty extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        EmptyView(
          icon: Icons.event_note_outlined,
          title: l10n.reservationsEmptyTitle,
          message: l10n.reservationsEmptyBody,
        ),
        PrimaryButton(
          label: l10n.reservationsFindCare,
          icon: Icons.search,
          onPressed: () async => context.go('/providers'),
        ),
      ],
    );
  }
}

class _List extends ConsumerWidget {
  const _List({required this.state, required this.onLoadMore});
  final PagedState<Reservation> state;
  final Future<void> Function() onLoadMore;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final now = ref.watch(nowProvider)();
    final upcoming = [
      for (final r in state.items)
        if (r.isUpcoming(now)) r,
    ];
    final past = [
      for (final r in state.items)
        if (!r.isUpcoming(now)) r,
    ];
    final rows = <Object>[
      if (upcoming.isNotEmpty) l10n.reservationsUpcoming,
      ...upcoming,
      if (past.isNotEmpty) l10n.reservationsPast,
      ...past,
    ];
    return ListView.builder(
      itemCount: rows.length + 1,
      itemBuilder: (context, index) {
        if (index == rows.length) {
          if (!state.hasMore) return const SizedBox(height: RacheetaSpacing.lg);
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: RacheetaSpacing.md),
            child: Column(
              children: [
                if (state.loadMoreError != null)
                  Text(
                    l10n.loadMoreFailed,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                if (state.loadingMore)
                  const CircularProgressIndicator()
                else
                  SecondaryButton(label: l10n.loadMore, onPressed: onLoadMore),
              ],
            ),
          );
        }
        final row = rows[index];
        if (row is String) {
          return Padding(
            padding: const EdgeInsets.only(
              top: RacheetaSpacing.md,
              bottom: RacheetaSpacing.sm,
            ),
            child: Semantics(
              header: true,
              child: Text(row, style: Theme.of(context).textTheme.titleMedium),
            ),
          );
        }
        return ReservationTile(reservation: row as Reservation);
      },
    );
  }
}

class ReservationTile extends ConsumerWidget {
  const ReservationTile({required this.reservation, super.key});
  final Reservation reservation;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final wallClock = ref.watch(wallClockProvider);
    return Card(
      margin: const EdgeInsets.only(bottom: RacheetaSpacing.md),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => context.push('/reservations/${reservation.id}'),
        child: Padding(
          padding: const EdgeInsets.all(RacheetaSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                reservation.providerName,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              Text(reservation.serviceTitle),
              Text(formatDateTime(reservation.startsAt, wallClock, locale)),
              const SizedBox(height: RacheetaSpacing.xs),
              StatusChip(status: reservation.status, l10n: l10n),
            ],
          ),
        ),
      ),
    );
  }
}

class StatusChip extends StatelessWidget {
  const StatusChip({required this.status, required this.l10n, super.key});
  final ReservationStatus status;
  final AppLocalizations l10n;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final color = switch (status) {
      ReservationStatus.confirmed ||
      ReservationStatus.completed => RacheetaColors.success,
      ReservationStatus.pending => RacheetaColors.warning,
      ReservationStatus.rejected ||
      ReservationStatus.cancelled ||
      ReservationStatus.noShow => scheme.error,
      ReservationStatus.unknown => scheme.onSurfaceVariant,
    };
    return Chip(
      label: Text(reservationStatusLabel(l10n, status)),
      side: BorderSide(color: color),
      labelStyle: TextStyle(color: color),
      visualDensity: VisualDensity.compact,
    );
  }
}
