import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/api/error_messages.dart';
import '../../chat/presentation/open_conversation_button.dart';
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
import '../application/reservation_actions.dart';
import '../application/reservation_providers.dart';
import '../data/reservation_models.dart';
import 'reservations_page.dart';

class ReservationDetailPage extends ConsumerWidget {
  const ReservationDetailPage({required this.reservationId, super.key});
  final String reservationId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final key = (account: ref.watch(accountIdProvider), id: reservationId);
    final detail = ref.watch(reservationDetailProvider(key));
    // While reloading (after a cancellation) the last value stays on screen so the page state
    // (its confirmation message) survives; the refreshed record replaces it when it arrives.
    if (detail.hasValue) {
      return _Detail(reservation: detail.requireValue);
    }
    if (detail.hasError) {
      final error = detail.error;
      return AppScaffold(
        title: l10n.reservationDetailTitle,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? apiErrorMessage(l10n, error)
              : l10n.errorUnknown,
          onRetry: () async => ref.invalidate(reservationDetailProvider(key)),
        ),
      );
    }
    return AppScaffold(
      title: l10n.reservationDetailTitle,
      body: const LoadingView(),
    );
  }
}

class _Detail extends ConsumerStatefulWidget {
  const _Detail({required this.reservation});
  final Reservation reservation;

  @override
  ConsumerState<_Detail> createState() => _DetailState();
}

class _DetailState extends ConsumerState<_Detail> {
  String? _message;
  bool _isError = false;

  Future<bool> _confirm() {
    final l10n = AppLocalizations.of(context);
    return showConfirmDialog(
      context,
      title: l10n.cancelConfirmTitle,
      message: l10n.cancelConfirmBody,
      confirmLabel: l10n.cancelConfirmAction,
      cancelLabel: l10n.cancelKeep,
    );
  }

  Future<void> _cancel() async {
    final l10n = AppLocalizations.of(context);
    setState(() => _message = null);
    try {
      await cancelReservation(ref, widget.reservation.id);
      if (mounted) {
        setState(() {
          _message = l10n.cancelSuccess;
          _isError = false;
        });
      }
    } on StaleSessionException {
      // Session ended while cancelling; the router has already moved to login.
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _message = apiErrorMessage(l10n, error);
        _isError = true;
      });
      // The backend refused (or the state changed elsewhere): show what is true now.
      ref.invalidate(reservationDetailProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final wallClock = ref.watch(wallClockProvider);
    final now = ref.watch(nowProvider)();
    final r = widget.reservation;
    // Offering the action is a convenience derived from the documented rule (live status, not yet
    // started). Whether it succeeds is decided by the backend alone.
    final offerCancel = r.isUpcoming(now);

    return AppScaffold(
      title: l10n.reservationDetailTitle,
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
                  key: const Key('reservation-message'),
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
                  _Row(l10n.reservationProvider, r.providerName),
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
                    _Row(l10n.reservationNote, r.patientNote),
                  const SizedBox(height: RacheetaSpacing.sm),
                  Row(
                    children: [
                      Text('${l10n.reservationStatus}: '),
                      StatusChip(status: r.status, l10n: l10n),
                    ],
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
          const SizedBox(height: RacheetaSpacing.xl),
          if (r.providerId != null)
            SecondaryButton(
              label: l10n.reservationViewProvider,
              onPressed: () async => context.push('/providers/${r.providerId}'),
            ),
          if (r.providerId != null) ...[
            const SizedBox(height: RacheetaSpacing.md),
            OpenConversationButton(
              reservationId: r.id,
              label: l10n.chatMessageProvider,
            ),
          ],
          if (offerCancel) ...[
            const SizedBox(height: RacheetaSpacing.md),
            PrimaryButton(
              label: l10n.cancelReservation,
              pendingLabel: l10n.cancellingReservation,
              icon: Icons.event_busy,
              confirm: _confirm,
              onPressed: _cancel,
            ),
          ],
        ],
      ),
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
