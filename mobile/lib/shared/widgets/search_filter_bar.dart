import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/generated/app_localizations.dart';
import '../search/search_query.dart';
import '../theme/app_theme.dart';
import 'async_action_button.dart';

/// One selectable value of a filter.
@immutable
class FilterOption {
  const FilterOption(this.value, this.label);
  final String value;
  final String label;
}

/// One dropdown of the filter sheet. [options] is null while its choices are still loading from
/// the backend (shown as loading) and [failed] marks a reference-data failure.
@immutable
class FilterField {
  const FilterField({
    required this.key,
    required this.label,
    required this.options,
    this.failed = false,
  });
  final String key;
  final String label;
  final List<FilterOption>? options;
  final bool failed;
}

/// Search box (debounced) plus a filter-sheet button with an active-filter badge. It edits a
/// [SearchQuery]; whoever owns the query decides what to do with it (normally a notifier that the
/// list controller watches, so a changed query restarts the list).
///
/// [scopeKey] is an opaque identity of whoever the query belongs to (the screens pass the
/// signed-in account id). When it changes while this bar stays mounted, everything typed or drafted
/// under the old scope is dropped: the pending debounce is cancelled, the box is re-synced to the
/// new query, and an open filter sheet is closed and its result ignored, so a value created under
/// account A can never update account B's query.
class SearchFilterBar extends ConsumerStatefulWidget {
  const SearchFilterBar({
    required this.query,
    required this.onChanged,
    required this.fieldsBuilder,
    required this.scopeKey,
    this.searchLabel,
    this.filtersTitle,
    this.showSearch = true,
    super.key,
  });

  final SearchQuery query;
  final ValueChanged<SearchQuery> onChanged;
  final List<FilterField> Function(WidgetRef ref, AppLocalizations l10n)
  fieldsBuilder;
  final String? searchLabel;
  final String? filtersTitle;
  final bool showSearch;
  final Object? scopeKey;

  @override
  ConsumerState<SearchFilterBar> createState() => _SearchFilterBarState();
}

class _SearchFilterBarState extends ConsumerState<SearchFilterBar> {
  static const _debounce = Duration(milliseconds: 400);
  late final TextEditingController _text = TextEditingController(
    text: widget.query.search,
  );
  Timer? _timer;
  BuildContext? _sheetContext;

  @override
  void didUpdateWidget(SearchFilterBar old) {
    super.didUpdateWidget(old);
    if (widget.scopeKey != old.scopeKey) {
      // New scope: nothing typed or drafted under the old one may reach the new query.
      _timer?.cancel();
      _text.text = widget.query.search;
      _closeOpenSheet();
    }
    // The owner reset the query (e.g. the account changed): keep the box in step.
    if (widget.query.search != old.query.search &&
        widget.query.search != _text.text) {
      _text.text = widget.query.search;
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _text.dispose();
    super.dispose();
  }

  /// Closes the filter sheet of the previous scope (only that route, after this frame).
  void _closeOpenSheet() {
    final sheet = _sheetContext;
    if (sheet == null) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!sheet.mounted) return;
      final route = ModalRoute.of(sheet);
      if (route != null && route.isActive) {
        Navigator.of(sheet).removeRoute(route);
      }
    });
  }

  void _apply(String text) {
    _timer?.cancel();
    if (widget.query.search == text) return;
    widget.onChanged(widget.query.withSearch(text));
  }

  Future<void> _openFilters() async {
    final openedFor = widget.scopeKey;
    final next = await showModalBottomSheet<SearchQuery>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheetContext) {
        _sheetContext = sheetContext;
        return _FilterSheet(
          initial: widget.query,
          title: widget.filtersTitle,
          fieldsBuilder: widget.fieldsBuilder,
        );
      },
    );
    _sheetContext = null;
    // A draft made under another scope (account) is never applied to the current one.
    if (next != null && mounted && widget.scopeKey == openedFor) {
      widget.onChanged(next);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final active = widget.query.activeFilterCount();
    return Row(
      children: [
        if (widget.showSearch)
          Expanded(
            child: TextField(
              key: const Key('search-field'),
              controller: _text,
              textInputAction: TextInputAction.search,
              onChanged: (text) {
                setState(() {});
                _timer?.cancel();
                _timer = Timer(_debounce, () => _apply(text));
              },
              onSubmitted: _apply,
              decoration: InputDecoration(
                labelText: widget.searchLabel ?? l10n.searchGenericHint,
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _text.text.isEmpty
                    ? null
                    : IconButton(
                        tooltip: l10n.searchClear,
                        icon: const Icon(Icons.close),
                        onPressed: () {
                          _text.clear();
                          _apply('');
                          setState(() {});
                        },
                      ),
              ),
            ),
          )
        else
          const Spacer(),
        const SizedBox(width: RacheetaSpacing.sm),
        Badge(
          isLabelVisible: active > 0,
          label: Text('$active'),
          child: IconButton.filledTonal(
            key: const Key('filters-button'),
            tooltip: l10n.filtersButton,
            icon: const Icon(Icons.tune),
            onPressed: _openFilters,
          ),
        ),
      ],
    );
  }
}

class _FilterSheet extends ConsumerStatefulWidget {
  const _FilterSheet({
    required this.initial,
    required this.fieldsBuilder,
    this.title,
  });
  final SearchQuery initial;
  final String? title;
  final List<FilterField> Function(WidgetRef ref, AppLocalizations l10n)
  fieldsBuilder;

  @override
  ConsumerState<_FilterSheet> createState() => _FilterSheetState();
}

class _FilterSheetState extends ConsumerState<_FilterSheet> {
  late SearchQuery _draft = widget.initial;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final fields = widget.fieldsBuilder(ref, l10n);
    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.viewInsetsOf(context).bottom,
        left: RacheetaSpacing.lg,
        right: RacheetaSpacing.lg,
        top: RacheetaSpacing.lg,
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            Semantics(
              header: true,
              child: Text(
                widget.title ?? l10n.filtersGenericTitle,
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            const SizedBox(height: RacheetaSpacing.lg),
            for (final field in fields) ...[
              if (field.failed)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(field.label),
                  subtitle: Text(l10n.filterLoadFailed),
                )
              else if (field.options == null)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(field.label),
                  subtitle: Text(l10n.loading),
                )
              else
                DropdownButtonFormField<String?>(
                  key: ValueKey(
                    '${field.key}-${_draft.filters[field.key] ?? 'any'}',
                  ),
                  initialValue: _draft.filters[field.key],
                  isExpanded: true,
                  decoration: InputDecoration(labelText: field.label),
                  items: [
                    DropdownMenuItem<String?>(
                      value: null,
                      child: Text(l10n.filterAny),
                    ),
                    for (final option in field.options!)
                      DropdownMenuItem<String?>(
                        value: option.value,
                        child: Text(option.label),
                      ),
                  ],
                  onChanged: (value) => setState(
                    () => _draft = _draft.withFilter(field.key, value),
                  ),
                ),
              const SizedBox(height: RacheetaSpacing.md),
            ],
            const SizedBox(height: RacheetaSpacing.sm),
            PrimaryButton(
              key: const Key('filters-apply'),
              label: l10n.filtersApply,
              onPressed: () async => Navigator.of(context).pop(_draft),
            ),
            const SizedBox(height: RacheetaSpacing.sm),
            SecondaryButton(
              label: l10n.filtersReset,
              onPressed: () async =>
                  Navigator.of(context).pop(widget.initial.cleared()),
            ),
            const SizedBox(height: RacheetaSpacing.lg),
          ],
        ),
      ),
    );
  }
}
