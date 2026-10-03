import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/time/time_providers.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/account_scope.dart';
import '../application/provider_actions.dart';
import '../application/provider_providers.dart';
import '../data/provider_models.dart';
import 'provider_errors.dart';
import 'provider_gate.dart';

/// Create one appointment slot: a service, a date and a start time (device time zone). The end
/// time, overlap checks and "must be in the future" are the backend's; this form only collects the
/// three inputs and sends the start as a UTC instant.
class SlotFormPage extends ConsumerWidget {
  const SlotFormPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return ProviderGate(title: l10n.slotFormTitle, child: const _SlotForm());
  }
}

class _SlotForm extends ConsumerStatefulWidget {
  const _SlotForm();

  @override
  ConsumerState<_SlotForm> createState() => _SlotFormState();
}

class _SlotFormState extends ConsumerState<_SlotForm> {
  String? _serviceId;
  DateTime? _date;
  TimeOfDay? _time;
  String? _message;
  bool _isError = false;

  /// Everything typed here belongs to one account: on logout or an account switch the choices and
  /// messages are discarded even though this page stays on screen.
  void _resetForAccountChange() => setState(() {
    _serviceId = null;
    _date = null;
    _time = null;
    _message = null;
    _isError = false;
  });

  DateTime? _startsAtUtc() {
    final date = _date;
    final time = _time;
    if (date == null || time == null) return null;
    return ref.read(localToUtcProvider)(
      DateTime(date.year, date.month, date.day, time.hour, time.minute),
    );
  }

  Future<void> _pickDate() async {
    final wallClock = ref.read(wallClockProvider);
    final today = wallClock(ref.read(nowProvider)());
    final first = DateTime(today.year, today.month, today.day);
    final picked = await showDatePicker(
      context: context,
      initialDate: _date ?? first.add(const Duration(days: 1)),
      firstDate: first,
      lastDate: first.add(const Duration(days: 365)),
    );
    if (picked != null && mounted) setState(() => _date = picked);
  }

  Future<void> _pickTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _time ?? const TimeOfDay(hour: 9, minute: 0),
    );
    if (picked != null && mounted) setState(() => _time = picked);
  }

  Future<void> _submit() async {
    final l10n = AppLocalizations.of(context);
    final serviceId = _serviceId;
    final startsAt = _startsAtUtc();
    if (serviceId == null || startsAt == null) return;
    final accountId = ref.read(accountIdProvider);
    setState(() => _message = null);
    try {
      await createSlot(ref, serviceId: serviceId, startsAt: startsAt);
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _message = l10n.slotCreated;
        _isError = false;
        _date = null;
        _time = null;
      });
    } on StaleSessionException {
      // The account changed while this was running: nothing to show.
    } on ApiException catch (error) {
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _message = providerErrorMessage(l10n, error, ProviderAction.createSlot);
        _isError = true;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    ref.listen<String?>(accountIdProvider, (previous, next) {
      if (previous != next) _resetForAccountChange();
    });
    final accountId = ref.watch(accountIdProvider);
    final services = ref.watch(ownServicesProvider(accountId));

    if (services.isLoading && !services.hasValue) {
      return AppScaffold(title: l10n.slotFormTitle, body: const LoadingView());
    }
    if (services.hasError && !services.hasValue) {
      final error = services.error;
      return AppScaffold(
        title: l10n.slotFormTitle,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? providerErrorMessage(l10n, error, ProviderAction.load)
              : l10n.errorUnknown,
          onRetry: () async => ref.invalidate(ownServicesProvider(accountId)),
        ),
      );
    }
    final usable = [
      for (final service in services.requireValue)
        if (service.canHaveSlots) service,
    ];
    if (usable.isEmpty) {
      return AppScaffold(
        title: l10n.slotFormTitle,
        scrollable: false,
        body: EmptyView(
          icon: Icons.medical_services_outlined,
          title: l10n.slotNoServices,
        ),
      );
    }

    final wallClock = ref.watch(wallClockProvider);
    final locale = Localizations.localeOf(context).languageCode;
    final startsAt = _startsAtUtc();
    final selected = _serviceId != null && usable.any((s) => s.id == _serviceId)
        ? _serviceId
        : null;
    OwnService? service;
    for (final candidate in usable) {
      if (candidate.id == selected) service = candidate;
    }

    return AppScaffold(
      title: l10n.slotFormTitle,
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
                  key: const Key('slot-form-message'),
                  style: TextStyle(
                    color: _isError
                        ? Theme.of(context).colorScheme.error
                        : RacheetaColors.success,
                  ),
                ),
              ),
            ),
          DropdownButtonFormField<String>(
            key: const Key('slot-service'),
            initialValue: selected,
            decoration: InputDecoration(labelText: l10n.slotService),
            items: [
              for (final s in usable)
                DropdownMenuItem(
                  value: s.id,
                  child: Text(
                    '${s.title} · ${l10n.serviceDuration(s.durationMinutes!)}',
                  ),
                ),
            ],
            onChanged: (value) => setState(() => _serviceId = value),
          ),
          const SizedBox(height: RacheetaSpacing.lg),
          // Local pickers, not backend actions: a plain button (no progress state while the
          // dialog is open).
          OutlinedButton.icon(
            key: const Key('slot-date'),
            icon: const Icon(Icons.calendar_today_outlined),
            label: Text(
              _date == null ? l10n.slotPickDate : formatDay(_date!, locale),
            ),
            onPressed: _pickDate,
          ),
          const SizedBox(height: RacheetaSpacing.md),
          OutlinedButton.icon(
            key: const Key('slot-time'),
            icon: const Icon(Icons.schedule),
            label: Text(
              _time == null
                  ? l10n.slotPickTime
                  : MaterialLocalizations.of(context).formatTimeOfDay(_time!),
            ),
            onPressed: _pickTime,
          ),
          const SizedBox(height: RacheetaSpacing.sm),
          Text(
            l10n.bookingTimezoneNote,
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: RacheetaSpacing.lg),
          if (service != null && startsAt != null)
            Padding(
              padding: const EdgeInsets.only(bottom: RacheetaSpacing.md),
              child: Text(
                '${service.title}: ${formatDateTime(startsAt, wallClock, locale)}',
                key: const Key('slot-summary'),
                style: Theme.of(context).textTheme.titleSmall,
              ),
            )
          else
            Padding(
              padding: const EdgeInsets.only(bottom: RacheetaSpacing.md),
              child: Text(l10n.slotSelectAll),
            ),
          PrimaryButton(
            key: const Key('slot-create'),
            label: l10n.slotCreate,
            pendingLabel: l10n.slotCreating,
            icon: Icons.event_available,
            onPressed: (service == null || startsAt == null) ? null : _submit,
          ),
          const SizedBox(height: RacheetaSpacing.md),
          SecondaryButton(
            label: l10n.slotBack,
            onPressed: () async => context.go('/workspace/availability'),
          ),
        ],
      ),
    );
  }
}
