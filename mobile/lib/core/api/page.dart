import 'package:flutter/foundation.dart';

/// The backend's standard pagination envelope: `{count, next, previous, results}`
/// (`StandardPagination`, 20 per page by default, `page_size` capped at 100 server-side).
@immutable
class Page<T> {
  const Page({
    required this.count,
    required this.next,
    required this.previous,
    required this.results,
  });

  factory Page.fromJson(Object? json, T Function(Object? item) parseItem) {
    if (json is! Map<String, Object?>) {
      throw const FormatException('Expected a paginated object.');
    }
    final results = json['results'];
    if (json['count'] is! int || results is! List) {
      throw const FormatException('Malformed paginated response.');
    }
    return Page<T>(
      count: json['count']! as int,
      next: json['next'] as String?,
      previous: json['previous'] as String?,
      results: List<T>.unmodifiable(results.map(parseItem)),
    );
  }

  final int count;
  final String? next;
  final String? previous;
  final List<T> results;

  bool get hasNext => next != null;
  bool get hasPrevious => previous != null;
}
