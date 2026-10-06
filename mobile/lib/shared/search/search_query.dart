import 'package:flutter/foundation.dart';

/// Search text plus a flat set of backend filter parameters (`name -> code`). Immutable and
/// comparable by value, so a notifier that watches it rebuilds (cancelling the old requests and
/// restarting pagination) exactly when the query really changes.
///
/// Every key is a query parameter the backend documents; nothing is filtered on the device.
@immutable
class SearchQuery {
  const SearchQuery({this.search = '', this.filters = const {}});

  final String search;
  final Map<String, String> filters;

  /// Narrowing filters in use. Parameters in [notCounted] (for example `ordering`) are not
  /// narrowing and do not count.
  int activeFilterCount({Set<String> notCounted = const {'ordering'}}) =>
      filters.keys
          .where((key) => !notCounted.contains(key) && filters[key]!.isNotEmpty)
          .length;

  bool get isEmpty => search.trim().isEmpty && filters.isEmpty;

  SearchQuery withSearch(String text) =>
      SearchQuery(search: text, filters: filters);

  /// Sets (or, with a null/empty [value], removes) one filter.
  SearchQuery withFilter(String key, String? value) {
    final next = Map<String, String>.of(filters);
    if (value == null || value.isEmpty) {
      next.remove(key);
    } else {
      next[key] = value;
    }
    return SearchQuery(search: search, filters: Map.unmodifiable(next));
  }

  /// Drops every narrowing filter (keeps the search text and the parameters in [keep]).
  SearchQuery cleared({Set<String> keep = const {'ordering'}}) => SearchQuery(
    search: search,
    filters: Map.unmodifiable({
      for (final entry in filters.entries)
        if (keep.contains(entry.key)) entry.key: entry.value,
    }),
  );

  /// The query-string parameters. [searchKey] is the backend's name for the text (`q`, `search`).
  Map<String, Object?> toQuery({String searchKey = 'search'}) => {
    if (search.trim().isNotEmpty) searchKey: search.trim(),
    ...filters,
  };

  @override
  bool operator ==(Object other) =>
      other is SearchQuery &&
      other.search == search &&
      mapEquals(other.filters, filters);

  @override
  int get hashCode => Object.hash(
    search,
    Object.hashAllUnordered(
      filters.entries.map((e) => Object.hash(e.key, e.value)),
    ),
  );
}
