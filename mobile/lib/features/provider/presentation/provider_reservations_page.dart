import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/paging/paged_notifier.dart';
import '../../../core/time/time_providers.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/states.dart';
import '../../reservations/presentation/reservations_page.dart';
import '../application/provider_providers.dart';
import '../data/provider_models.dart';
import 'provider_errors.dart';
import 'provider_gate.dart';

/// Reservations received by the provider's own profile, in the backend's order (newest
/// appointment first). Only fields of the provider reservation schema are shown.
class ProviderReservationsPage extends ConsumerWidget {
  const ProviderReservationsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return ProviderGate(title: l10n.bookingsTitle, child: const _List());
  }
}

class _List extends ConsumerWidget {
  const _List();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final state = ref.watch(providerReservationListProvider);
    final controller = ref.read(providerReservationListProvider.notifier);

    switch (state.phase) {
      case PagedPhase.loading:
        return AppScaffold(
          title: l10n.bookingsTitle,
          body: const LoadingView(),
        );
      case PagedPhase.error:
        return AppScaffold(
          title: l10n.bookingsTitle,
          scrollable: false,
          body: ErrorView(
            message: providerErrorMessage(
              l10n,
              state.error!,
              ProviderAction.load,
            ),
            onRetry: () async => controller.reload(),
          ),
        );
      case PagedPhase.ready:
        break;
    }
    if (state.items.isEmpty) {
      return AppScaffold(
        title: l10n.bookingsTitle,
        scrollable: false,
        body: EmptyView(
          icon: Icons.event_note_outlined,
          title: l10n.bookingsEmptyTitle,
          message: l10n.bookingsEmptyBody,
        ),
      );
    }
    return AppScaffold(
      title: l10n.bookingsTitle,
      scrollable: false,
      body: RefreshIndicator(
        onRefresh: () async => controller.reload(),
        child: ListView.builder(
          itemCount: state.items.length + 1,
          itemBuilder: (context, index) {
            if (index == state.items.length) {
              if (!state.hasMore) {
                return Padding(
                  padding: const EdgeInsets.only(top: RacheetaSpacing.md),
                  child: Text(
                    l10n.bookingTimezoneNote,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                );
              }
              return Padding(
                padding: const EdgeInsets.symmetric(
                  vertical: RacheetaSpacing.md,
                ),
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
                      SecondaryButton(
                        label: l10n.loadMore,
                        onPressed: controller.loadMore,
                      ),
                  ],
                ),
              );
            }
            return _Tile(item: state.items[index]);
          },
        ),
      ),
    );
  }
}

class _Tile extends ConsumerWidget {
  const _Tile({required this.item});
  final ProviderReservation item;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final wallClock = ref.watch(wallClockProvider);
    final r = item.reservation;
    return Card(
      margin: const EdgeInsets.only(bottom: RacheetaSpacing.md),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => context.push('/workspace/reservations/${r.id}'),
        child: Padding(
          padding: const EdgeInsets.all(RacheetaSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                item.patientName,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              Text(r.serviceTitle),
              Text(formatDateTime(r.startsAt, wallClock, locale)),
              const SizedBox(height: RacheetaSpacing.xs),
              StatusChip(status: r.status, l10n: l10n),
            ],
          ),
        ),
      ),
    );
  }
}
