import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/labels.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../application/discovery_providers.dart';
import '../data/discovery_api.dart';
import '../data/discovery_models.dart';

const _providerTypes = <String>[
  'DOCTOR',
  'NURSE',
  'THERAPIST',
  'HOSPITAL',
  'MEDICAL_CENTER',
  'PHARMACY',
  'LABORATORY',
  'BEAUTY_CENTER',
];

/// Modal sheet that edits a *draft* of the filters; nothing is queried until "Apply".
Future<DiscoveryFilters?> showFiltersSheet(
  BuildContext context,
  DiscoveryFilters current,
) => showModalBottomSheet<DiscoveryFilters>(
  context: context,
  isScrollControlled: true,
  useSafeArea: true,
  builder: (_) => FiltersSheet(initial: current),
);

class FiltersSheet extends ConsumerStatefulWidget {
  const FiltersSheet({required this.initial, super.key});
  final DiscoveryFilters initial;

  @override
  ConsumerState<FiltersSheet> createState() => _FiltersSheetState();
}

class _FiltersSheetState extends ConsumerState<FiltersSheet> {
  late DiscoveryFilters _draft = widget.initial;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final language = Localizations.localeOf(context).languageCode;
    final specialties = ref.watch(specialtiesProvider);
    final governorates = ref.watch(governoratesProvider);
    final governorateId = _draft.governorateId;
    final cities = governorateId == null
        ? null
        : ref.watch(citiesProvider(governorateId));

    DropdownMenuItem<String?> any() =>
        DropdownMenuItem<String?>(value: null, child: Text(l10n.filterAny));

    Widget field({
      required String label,
      required String? value,
      required List<DropdownMenuItem<String?>> items,
      required ValueChanged<String?> onChanged,
      AsyncValue<Object?>? source,
    }) {
      if (source != null && source.hasError) {
        return ListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(label),
          subtitle: Text(l10n.filterLoadFailed),
        );
      }
      return DropdownButtonFormField<String?>(
        key: ValueKey('$label-${value ?? 'any'}'),
        initialValue: value,
        isExpanded: true,
        decoration: InputDecoration(labelText: label),
        items: [any(), ...items],
        onChanged: onChanged,
      );
    }

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(RacheetaSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Semantics(
              header: true,
              child: Text(
                l10n.filtersTitle,
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            const SizedBox(height: RacheetaSpacing.lg),
            field(
              label: l10n.filterKind,
              value: _draft.kind,
              items: [
                DropdownMenuItem(
                  value: 'PRACTITIONER',
                  child: Text(l10n.kindPractitioner),
                ),
                DropdownMenuItem(
                  value: 'FACILITY',
                  child: Text(l10n.kindFacility),
                ),
              ],
              onChanged: (v) =>
                  setState(() => _draft = _draft.copyWith(kind: v)),
            ),
            const SizedBox(height: RacheetaSpacing.md),
            field(
              label: l10n.filterType,
              value: _draft.type,
              items: [
                for (final code in _providerTypes)
                  DropdownMenuItem(
                    value: code,
                    child: Text(providerTypeLabel(l10n, code)),
                  ),
              ],
              onChanged: (v) =>
                  setState(() => _draft = _draft.copyWith(type: v)),
            ),
            const SizedBox(height: RacheetaSpacing.md),
            field(
              label: l10n.filterSpecialty,
              value: _draft.specialtySlug,
              source: specialties,
              items: [
                for (final s in specialties.value ?? const <Specialty>[])
                  DropdownMenuItem(
                    value: s.slug,
                    child: Text(s.name(language)),
                  ),
              ],
              onChanged: (v) =>
                  setState(() => _draft = _draft.copyWith(specialtySlug: v)),
            ),
            const SizedBox(height: RacheetaSpacing.md),
            field(
              label: l10n.filterGovernorate,
              value: _draft.governorateId,
              source: governorates,
              items: [
                for (final g in governorates.value ?? const <Place>[])
                  DropdownMenuItem(value: g.id, child: Text(g.name(language))),
              ],
              onChanged: (v) =>
                  setState(() => _draft = _draft.copyWith(governorateId: v)),
            ),
            if (cities != null) ...[
              const SizedBox(height: RacheetaSpacing.md),
              field(
                label: l10n.filterCity,
                value: _draft.cityId,
                source: cities,
                items: [
                  for (final c in cities.value ?? const <Place>[])
                    DropdownMenuItem(
                      value: c.id,
                      child: Text(c.name(language)),
                    ),
                ],
                onChanged: (v) =>
                    setState(() => _draft = _draft.copyWith(cityId: v)),
              ),
            ],
            const SizedBox(height: RacheetaSpacing.md),
            DropdownButtonFormField<DiscoveryOrdering>(
              initialValue: _draft.ordering,
              isExpanded: true,
              decoration: InputDecoration(labelText: l10n.sortLabel),
              items: [
                for (final o in DiscoveryOrdering.values)
                  DropdownMenuItem(
                    value: o,
                    child: Text(_orderingLabel(l10n, o)),
                  ),
              ],
              onChanged: (v) {
                if (v != null) {
                  setState(() => _draft = _draft.copyWith(ordering: v));
                }
              },
            ),
            const SizedBox(height: RacheetaSpacing.xl),
            PrimaryButton(
              label: l10n.filtersApply,
              onPressed: () async => Navigator.of(context).pop(_draft),
            ),
            const SizedBox(height: RacheetaSpacing.sm),
            SecondaryButton(
              label: l10n.filtersReset,
              onPressed: () async =>
                  Navigator.of(context)
                      .pop(DiscoveryFilters(search: widget.initial.search)),
            ),
          ],
        ),
      ),
    );
  }
}

String _orderingLabel(AppLocalizations l10n, DiscoveryOrdering ordering) =>
    switch (ordering) {
      DiscoveryOrdering.nameAsc => l10n.sortNameAsc,
      DiscoveryOrdering.nameDesc => l10n.sortNameDesc,
      DiscoveryOrdering.newest => l10n.sortNewest,
      DiscoveryOrdering.oldest => l10n.sortOldest,
    };
