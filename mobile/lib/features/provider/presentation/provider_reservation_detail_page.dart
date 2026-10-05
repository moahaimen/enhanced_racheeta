import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/time/time_providers.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/format/labels.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/confirm_dialog.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/account_scope.dart';
import '../../reservations/data/reservation_models.dart';
import '../../reservations/presentation/reservations_page.dart';
import '../application/provider_actions.dart';
import '../application/provider_providers.dart';
import '../data/provider_models.dart';
import '../data/provider_transitions.dart';
import 'provider_errors.dart';
import 'provider_gate.dart';

class ProviderReservationDetailPage extends ConsumerWidget {
  const ProviderReservationDetailPage({required this.reservationId, super.key});
  final String reservationId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return ProviderGate(
      title: l10n.bookingDetailTitle,
      child: _Detail(reservationId: reservationId),
    );
  }
}

class _Detail extends ConsumerStatefulWidget {
  const _Detail({required this.reservationId});
  final String reservationId;

  @override
  ConsumerState<_Detail> createState() => _DetailState();
}

class _DetailState extends ConsumerState<_Detail> {
  String? _message;
  bool _isError = false;
  bool _busy = false;

  /// Messages and the busy flag belong to one account.
  void _resetForAccountChange() => setState(() {
    _message = null;
    _isError = false;
    _busy = false;
  });

  Future<bool> _confirm(ReservationStatus target) {
    final l10n = AppLocalizations.of(context);
    final (title, body, action) = switch (target) {
      ReservationStatus.rejected => (
        l10n.confirmRejectTitle,
        l10n.confirmRejectBody,
        l10n.actionReject,
      ),
      ReservationStatus.noShow => (
        l10n.confirmNoShowTitle,
        l10n.confirmNoShowBody,
        l10n.actionNoShow,
      ),
      _ => (
        l10n.confirmCancelBookingTitle,
        l10n.confirmCancelBookingBody,
        l10n.actionCancelBooking,
      ),
    };
    return showConfirmDialog(
      context,
      title: title,
      message: body,
      confirmLabel: action,
      cancelLabel: l10n.confirmKeep,
    );
  }

  Future<void> _transition(ReservationStatus target) async {
    final l10n = AppLocalizations.of(context);
    final accountId = ref.read(accountIdProvider);
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await transitionReservation(
        ref,
        id: widget.reservationId,
        target: target,
      );
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _busy = false;
        _message = l10n.transitionDone;
        _isError = false;
      });
    } on StaleSessionException {
      // The account changed while this was running: its result is never shown to the new one.
    } on ApiException catch (error) {
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _busy = false;
        _message = providerErrorMessage(l10n, error, ProviderAction.transition);
        _isError = true;
      });
      // The backend refused (or the state changed elsewhere): show what is true now.
      ref.invalidate(providerReservationDetailProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    ref.listen<String?>(accountIdProvider, (previous, next) {
      if (previous != next) _resetForAccountChange();
    });
    final accountId = ref.watch(accountIdProvider);
    final key = (account: accountId, value: widget.reservationId);
    final detail = ref.watch(providerReservationDetailProvider(key));

    // Keyed by account: a value here always belongs to the signed-in account. During a reload
    // (after a transition) the last value stays so the page message survives.
    if (detail.hasValue) return _content(context, detail.requireValue);
    if (detail.hasError && !detail.isLoading) {
      final error = detail.error;
      return AppScaffold(
        title: l10n.bookingDetailTitle,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? providerErrorMessage(l10n, error, ProviderAction.load)
              : l10n.errorUnknown,
          onRetry: () async =>
              ref.invalidate(providerReservationDetailProvider(key)),
        ),
      );
    }
    return AppScaffold(
      title: l10n.bookingDetailTitle,
      body: const LoadingView(),
    );
  }

  Widget _content(BuildContext context, ProviderReservation item) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final wallClock = ref.watch(wallClockProvider);
    final now = ref.watch(nowProvider)();
    final r = item.reservation;
    final offered = offeredTransitions(r, now);

    return AppScaffold(
      title: l10n.bookingDetailTitle,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_message != null)
            Padding(
              padding: const EdgeInsets.only(bottom: RacheetaSpacing.md),
              child: Semantics(
                liveRegion: true,
                child: Text(
                  _message!,
                  key: const Key('booking-message'),
                  style: TextStyle(
                    color: _isError
                        ? theme.colorScheme.error
                        : RacheetaColors.success,
                  ),
                ),
              ),
            ),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(RacheetaSpacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _Row(l10n.patientLabel, item.patientName),
                  _Row(l10n.reservationService, r.serviceTitle),
                  _Row(
                    l10n.reservationWhen,
                    formatDateTime(r.startsAt, wallClock, locale),
                  ),
                  if (r.durationMinutes != null)
                    _Row(
                      l10n.reservationDuration,
                      l10n.serviceDuration(r.durationMinutes!),
                    ),
                  _Row(
                    l10n.reservationPrice,
                    formatMoney(r.price, r.currency, locale),
                  ),
                  if (r.patientNote.isNotEmpty)
                    _Row(l10n.patientNoteLabel, r.patientNote),
                  const SizedBox(height: RacheetaSpacing.sm),
                  Row(
                    children: [
                      Text('${l10n.reservationStatus}: '),
                      StatusChip(status: r.status, l10n: l10n),
                    ],
                  ),
                  const SizedBox(height: RacheetaSpacing.sm),
                  Text(
                    l10n.bookingTimezoneNote,
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ),
          if (r.transitions.isNotEmpty) ...[
            const SizedBox(height: RacheetaSpacing.lg),
            Semantics(
              header: true,
              child: Text(
                l10n.reservationHistory,
                style: theme.textTheme.titleMedium,
              ),
            ),
            for (final t in r.transitions)
              ListTile(
                contentPadding: EdgeInsets.zero,
                dense: true,
                title: Text(reservationStatusLabel(l10n, t.to)),
                subtitle: Text(formatDateTime(t.createdAt, wallClock, locale)),
              ),
          ],
          if (offered.isNotEmpty) ...[
            const SizedBox(height: RacheetaSpacing.xl),
            for (final target in offered) ...[
              _TransitionButton(
                target: target,
                enabled: !_busy,
                confirm: switch (target) {
                  ReservationStatus.rejected ||
                  ReservationStatus.cancelled ||
                  ReservationStatus.noShow => () => _confirm(target),
                  _ => null,
                },
                onPressed: () => _transition(target),
              ),
              const SizedBox(height: RacheetaSpacing.md),
            ],
          ],
        ],
      ),
    );
  }
}

class _TransitionButton extends StatelessWidget {
  const _TransitionButton({
    required this.target,
    required this.enabled,
    required this.onPressed,
    this.confirm,
  });

  final ReservationStatus target;
  final bool enabled;
  final Future<void> Function() onPressed;
  final Future<bool> Function()? confirm;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final (label, pending, icon, primary) = switch (target) {
      ReservationStatus.confirmed => (
        l10n.actionConfirm,
        l10n.actionConfirming,
        Icons.check_circle_outline,
        true,
      ),
      ReservationStatus.completed => (
        l10n.actionComplete,
        l10n.actionUpdating,
        Icons.task_alt,
        true,
      ),
      ReservationStatus.rejected => (
        l10n.actionReject,
        l10n.actionUpdating,
        Icons.block,
        false,
      ),
      ReservationStatus.noShow => (
        l10n.actionNoShow,
        l10n.actionUpdating,
        Icons.person_off_outlined,
        false,
      ),
      _ => (
        l10n.actionCancelBooking,
        l10n.actionUpdating,
        Icons.event_busy,
        false,
      ),
    };
    final handler = enabled ? onPressed : null;
    return primary
        ? PrimaryButton(
            key: Key('transition-${target.wire}'),
            label: label,
            pendingLabel: pending,
            icon: icon,
            confirm: confirm,
            onPressed: handler,
          )
        : SecondaryButton(
            key: Key('transition-${target.wire}'),
            label: label,
            pendingLabel: pending,
            icon: icon,
            confirm: confirm,
            onPressed: handler,
          );
  }
}

class _Row extends StatelessWidget {
  const _Row(this.label, this.value);
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: RacheetaSpacing.sm),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: Theme.of(context).textTheme.bodySmall
              ?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
        ),
        Text(value),
      ],
    ),
  );
}
