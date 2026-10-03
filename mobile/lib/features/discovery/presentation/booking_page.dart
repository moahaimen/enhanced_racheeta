import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/api/error_messages.dart';
import '../../../core/time/instants.dart';
import '../../../core/time/time_providers.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/providers.dart';
import '../../auth/application/session_state.dart';
import '../../reservations/application/reservation_actions.dart';
import '../../reservations/data/reservation_models.dart';
import '../application/discovery_providers.dart';
import '../data/discovery_models.dart';
import 'provider_detail_page.dart';

/// Appointment selection and booking for one provider service. Slots are exactly what
/// `GET /providers/{id}/availability` returned; none are generated. A listed slot is a snapshot:
/// the backend re-validates on `POST /reservations` and its answer is final.
class BookingPage extends ConsumerStatefulWidget {
  const BookingPage({
    required this.providerId,
    required this.serviceId,
    super.key,
  });
  final String providerId;
  final String serviceId;

  @override
  ConsumerState<BookingPage> createState() => _BookingPageState();
}

class _BookingPageState extends ConsumerState<BookingPage> {
  final TextEditingController _note = TextEditingController();
  DateTime? _day;
  String? _slotId;
  String? _banner;
  String? _noteError;
  Reservation? _created;

  AvailabilityQuery get _query =>
      (providerId: widget.providerId, serviceId: widget.serviceId);

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    setState(() {
      _slotId = null;
      _banner = null;
    });
    ref.invalidate(availabilityProvider(_query));
  }

  Future<void> _submit() async {
    final l10n = AppLocalizations.of(context);
    final slotId = _slotId;
    if (slotId == null) return;
    if (_note.text.trim().length > maxPatientNoteLength) {
      setState(
        () => _noteError = l10n.bookingNoteTooLong(maxPatientNoteLength),
      );
      return;
    }
    setState(() {
      _noteError = null;
      _banner = null;
    });
    try {
      final reservation = await bookSlot(ref, slotId: slotId, note: _note.text);
      if (mounted) setState(() => _created = reservation);
    } on StaleSessionException {
      // Signed out / switched account while booking: nothing to show for the old session.
    } on ApiException catch (error) {
      if (!mounted) return;
      final isConflict =
          error.code == 'slot_unavailable' || error.code == 'slot_conflict';
      setState(() {
        _noteError = error.fieldError('patient_note');
        _banner =
            _noteError != null && error.fieldError('availability_slot') == null
            ? null
            : apiErrorMessage(l10n, error);
        if (isConflict || error.kind == ApiErrorKind.notFound) _slotId = null;
      });
      if (isConflict) ref.invalidate(availabilityProvider(_query));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final session = ref.watch(sessionControllerProvider);
    final canBook =
        session is SessionAuthenticated &&
        session.account.hasPermission(bookingCapability);
    if (!canBook) {
      return AppScaffold(
        title: l10n.bookingTitle,
        scrollable: false,
        body: EmptyView(
          icon: Icons.lock_outline,
          title: l10n.bookingPatientsOnly,
        ),
      );
    }
    if (_created != null) {
      return AppScaffold(
        title: l10n.bookingTitle,
        body: _Success(reservation: _created!),
      );
    }

    final provider = ref.watch(providerDetailProvider(widget.providerId));
    final slots = ref.watch(availabilityProvider(_query));
    final failure = provider.error ?? slots.error;
    if (failure != null) {
      return AppScaffold(
        title: l10n.bookingTitle,
        scrollable: false,
        body: ErrorView(
          message: failure is ApiException
              ? apiErrorMessage(l10n, failure)
              : l10n.errorUnknown,
          onRetry: () async {
            ref
              ..invalidate(providerDetailProvider(widget.providerId))
              ..invalidate(availabilityProvider(_query));
          },
        ),
      );
    }
    if (provider.isLoading ||
        slots.isLoading ||
        !provider.hasValue ||
        !slots.hasValue) {
      return AppScaffold(title: l10n.bookingTitle, body: const LoadingView());
    }
    PublicService? service;
    for (final candidate in provider.requireValue.services) {
      if (candidate.id == widget.serviceId) service = candidate;
    }
    if (service == null) {
      return AppScaffold(
        title: l10n.bookingTitle,
        scrollable: false,
        body: EmptyView(icon: Icons.search_off, title: l10n.errorNotFound),
      );
    }
    return AppScaffold(
      title: l10n.bookingTitle,
      body: _form(context, provider.requireValue, service, slots.requireValue),
    );
  }

  Widget _form(
    BuildContext context,
    ProviderPublic provider,
    PublicService service,
    List<AvailabilitySlot> slots,
  ) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final wallClock = ref.watch(wallClockProvider);

    // Group by the user's local calendar day (timezone policy: core/time/instants.dart).
    final byDay = <DateTime, List<AvailabilitySlot>>{};
    for (final slot in slots) {
      byDay.putIfAbsent(dayOf(wallClock(slot.startsAt)), () => []).add(slot);
    }
    final days = byDay.keys.toList()..sort();
    final day = (_day != null && byDay.containsKey(_day))
        ? _day
        : (days.isEmpty ? null : days.first);
    final daySlots = day == null ? const <AvailabilitySlot>[] : byDay[day]!;
    AvailabilitySlot? selected;
    for (final slot in slots) {
      if (slot.id == _slotId) selected = slot;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(RacheetaSpacing.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  provider.card.displayName,
                  style: theme.textTheme.titleMedium,
                ),
                Text(service.title),
                Text(
                  [
                    formatMoney(service.price, service.currency, locale),
                    if (service.durationMinutes != null)
                      l10n.serviceDuration(service.durationMinutes!),
                  ].join(' · '),
                ),
              ],
            ),
          ),
        ),
        if (_banner != null)
          Padding(
            padding: const EdgeInsets.only(top: RacheetaSpacing.md),
            child: Semantics(
              liveRegion: true,
              child: Text(
                _banner!,
                key: const Key('booking-banner'),
                style: TextStyle(color: theme.colorScheme.error),
              ),
            ),
          ),
        const SizedBox(height: RacheetaSpacing.lg),
        if (slots.isEmpty) ...[
          EmptyView(
            icon: Icons.event_busy,
            title: l10n.bookingNoSlots,
            message: l10n.bookingNoSlotsHint,
          ),
          SecondaryButton(
            label: l10n.bookingRefresh,
            icon: Icons.refresh,
            onPressed: _refresh,
          ),
        ] else ...[
          Semantics(
            header: true,
            child: Text(
              l10n.bookingChooseDay,
              style: theme.textTheme.titleSmall,
            ),
          ),
          const SizedBox(height: RacheetaSpacing.sm),
          Wrap(
            spacing: RacheetaSpacing.sm,
            runSpacing: RacheetaSpacing.sm,
            children: [
              for (final d in days)
                ChoiceChip(
                  label: Text(formatDay(d, locale)),
                  selected: d == day,
                  onSelected: (_) => setState(() {
                    _day = d;
                    _slotId = null;
                  }),
                ),
            ],
          ),
          const SizedBox(height: RacheetaSpacing.lg),
          Semantics(
            header: true,
            child: Text(
              l10n.bookingChooseTime,
              style: theme.textTheme.titleSmall,
            ),
          ),
          const SizedBox(height: RacheetaSpacing.sm),
          Wrap(
            spacing: RacheetaSpacing.sm,
            runSpacing: RacheetaSpacing.sm,
            children: [
              for (final slot in daySlots)
                ChoiceChip(
                  label: Text(formatTime(slot.startsAt, wallClock, locale)),
                  selected: slot.id == _slotId,
                  onSelected: (_) => setState(() => _slotId = slot.id),
                ),
            ],
          ),
          const SizedBox(height: RacheetaSpacing.sm),
          Text(
            l10n.bookingTimezoneNote,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: RacheetaSpacing.lg),
          TextField(
            controller: _note,
            minLines: 2,
            maxLines: 4,
            keyboardType: TextInputType.multiline,
            decoration: InputDecoration(
              labelText: l10n.bookingNote,
              errorText: _noteError,
              errorMaxLines: 3,
            ),
          ),
          const SizedBox(height: RacheetaSpacing.lg),
          if (selected != null)
            Padding(
              padding: const EdgeInsets.only(bottom: RacheetaSpacing.md),
              child: Text(
                '${l10n.bookingSummary}: ${formatDateTime(selected.startsAt, wallClock, locale)}',
                key: const Key('booking-summary'),
                style: theme.textTheme.titleSmall,
              ),
            )
          else
            Padding(
              padding: const EdgeInsets.only(bottom: RacheetaSpacing.md),
              child: Text(l10n.bookingSelectSlot),
            ),
          PrimaryButton(
            label: l10n.bookingConfirm,
            pendingLabel: l10n.bookingConfirming,
            icon: Icons.event_available,
            onPressed: selected == null ? null : _submit,
          ),
        ],
      ],
    );
  }
}

class _Success extends StatelessWidget {
  const _Success({required this.reservation});
  final Reservation reservation;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Icon(Icons.check_circle_outline, size: 56),
        const SizedBox(height: RacheetaSpacing.lg),
        Semantics(
          liveRegion: true,
          child: Text(
            l10n.bookingSuccessTitle,
            key: const Key('booking-success'),
            style: Theme.of(context).textTheme.titleLarge,
            textAlign: TextAlign.center,
          ),
        ),
        const SizedBox(height: RacheetaSpacing.sm),
        Text(l10n.bookingSuccessBody, textAlign: TextAlign.center),
        const SizedBox(height: RacheetaSpacing.xl),
        PrimaryButton(
          label: l10n.bookingViewReservation,
          onPressed: () async => context.go('/reservations/${reservation.id}'),
        ),
      ],
    );
  }
}
