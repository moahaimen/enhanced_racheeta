import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/paging/paged_notifier.dart';
import '../../../core/time/instants.dart';
import '../../../core/time/time_providers.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/confirm_dialog.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/account_scope.dart';
import '../application/provider_actions.dart';
import '../application/provider_providers.dart';
import '../data/provider_models.dart';
import 'provider_errors.dart';
import 'provider_gate.dart';

/// The provider's appointment availability. Everything shown is what
/// `GET /reservations/provider/availability` returned (nothing is generated here); the list shows
/// the active slots that have not ended, grouped by the device's local day.
class AvailabilityPage extends ConsumerWidget {
  const AvailabilityPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return ProviderGate(
      title: l10n.scheduleTitle,
      child: const _AvailabilityBody(),
    );
  }
}

class _AvailabilityBody extends ConsumerStatefulWidget {
  const _AvailabilityBody();

  @override
  ConsumerState<_AvailabilityBody> createState() => _AvailabilityBodyState();
}

class _AvailabilityBodyState extends ConsumerState<_AvailabilityBody> {
  String? _message;
  bool _isError = false;

  void _resetForAccountChange() => setState(() => _message = null);

  Future<void> _remove(ProviderSlot slot) async {
    final l10n = AppLocalizations.of(context);
    final accountId = ref.read(accountIdProvider);
    setState(() => _message = null);
    try {
      await deactivateSlot(ref, slot.id);
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _message = l10n.slotRemoved;
        _isError = false;
      });
    } on StaleSessionException {
      // The account changed (or the session ended) while this was running: nothing to show.
    } on ApiException catch (error) {
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _message = providerErrorMessage(
          l10n,
          error,
          ProviderAction.deactivateSlot,
        );
        _isError = true;
      });
      // The slot may be gone or changed elsewhere: show what is true now.
      if (error.kind == ApiErrorKind.notFound) invalidateProviderSlots(ref);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    ref.listen<String?>(accountIdProvider, (previous, next) {
      if (previous != next) _resetForAccountChange();
    });
    final state = ref.watch(providerSlotsProvider);
    final controller = ref.read(providerSlotsProvider.notifier);

    switch (state.phase) {
      case PagedPhase.loading:
        return AppScaffold(
          title: l10n.scheduleTitle,
          body: const LoadingView(),
        );
      case PagedPhase.error:
        return AppScaffold(
          title: l10n.scheduleTitle,
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

    final now = ref.watch(nowProvider)();
    final wallClock = ref.watch(wallClockProvider);
    final locale = Localizations.localeOf(context).languageCode;
    final upcoming = [
      for (final slot in state.items)
        if (slot.isCurrent(now)) slot,
    ];
    final byDay = <DateTime, List<ProviderSlot>>{};
    for (final slot in upcoming) {
      byDay.putIfAbsent(dayOf(wallClock(slot.startsAt)), () => []).add(slot);
    }
    final days = byDay.keys.toList()..sort();

    return AppScaffold(
      title: l10n.scheduleTitle,
      scrollable: false,
      body: RefreshIndicator(
        onRefresh: () async => controller.reload(),
        child: ListView(
          children: [
            PrimaryButton(
              label: l10n.scheduleAdd,
              icon: Icons.add,
              onPressed: () async =>
                  context.push('/workspace/availability/new'),
            ),
            if (_message != null)
              Padding(
                padding: const EdgeInsets.only(top: RacheetaSpacing.md),
                child: Semantics(
                  liveRegion: true,
                  child: Text(
                    _message!,
                    key: const Key('schedule-message'),
                    style: TextStyle(
                      color: _isError
                          ? Theme.of(context).colorScheme.error
                          : RacheetaColors.success,
                    ),
                  ),
                ),
              ),
            const SizedBox(height: RacheetaSpacing.md),
            if (upcoming.isEmpty) ...[
              EmptyView(
                icon: Icons.event_busy,
                title: state.hasMore
                    ? l10n.scheduleNoneLoaded
                    : l10n.scheduleEmptyTitle,
                message: state.hasMore ? null : l10n.scheduleEmptyBody,
              ),
            ] else ...[
              for (final day in days) ...[
                Padding(
                  padding: const EdgeInsets.only(
                    top: RacheetaSpacing.md,
                    bottom: RacheetaSpacing.sm,
                  ),
                  child: Semantics(
                    header: true,
                    child: Text(
                      formatDay(day, locale),
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                ),
                for (final slot in byDay[day]!)
                  _SlotTile(slot: slot, onRemove: () => _remove(slot)),
              ],
              Padding(
                padding: const EdgeInsets.only(top: RacheetaSpacing.md),
                child: Text(
                  l10n.bookingTimezoneNote,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            ],
            if (state.hasMore)
              Padding(
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
              ),
          ],
        ),
      ),
    );
  }
}

class _SlotTile extends ConsumerWidget {
  const _SlotTile({required this.slot, required this.onRemove});
  final ProviderSlot slot;
  final Future<void> Function() onRemove;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final wallClock = ref.watch(wallClockProvider);
    final start = formatTime(slot.startsAt, wallClock, locale);
    final end = formatTime(slot.endsAt, wallClock, locale);
    return Card(
      key: Key('slot-${slot.id}'),
      margin: const EdgeInsets.only(bottom: RacheetaSpacing.sm),
      child: Padding(
        padding: const EdgeInsets.all(RacheetaSpacing.md),
        // The shared buttons are full-width by theme, so the action sits below the details
        // instead of in a Row (which would give it unbounded width).
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '$start – $end',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            Text(slot.serviceTitle),
            if (slot.durationMinutes != null)
              Text(l10n.serviceDuration(slot.durationMinutes!)),
            const SizedBox(height: RacheetaSpacing.sm),
            SecondaryButton(
              label: l10n.slotRemove,
              pendingLabel: l10n.slotRemoving,
              icon: Icons.delete_outline,
              confirm: () => showConfirmDialog(
                context,
                title: l10n.slotRemoveConfirmTitle,
                message: l10n.slotRemoveConfirmBody,
                confirmLabel: l10n.slotRemoveAction,
                cancelLabel: l10n.slotKeep,
              ),
              onPressed: onRemove,
            ),
          ],
        ),
      ),
    );
  }
}
