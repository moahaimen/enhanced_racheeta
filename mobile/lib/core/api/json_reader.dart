// Strict, typed access to a decoded JSON object. A missing or mistyped *required* field is a
// [FormatException] (surfaced as an unreadable response), never a silent default.
import '../time/instants.dart';

final class JsonReader {
  JsonReader._(this._map, this._what);

  factory JsonReader.of(Object? json, String what) {
    if (json is Map<String, Object?>) return JsonReader._(json, what);
    throw FormatException('Expected an object for $what.');
  }

  final Map<String, Object?> _map;
  final String _what;

  Never _bad(String key) => throw FormatException('Bad "$key" in $_what.');

  String string(String key) {
    final value = _map[key];
    return value is String ? value : _bad(key);
  }

  String stringOr(String key, [String fallback = '']) {
    final value = _map[key];
    return value is String ? value : fallback;
  }

  String? stringOrNull(String key) {
    final value = _map[key];
    return value is String ? value : null;
  }

  bool boolean(String key) {
    final value = _map[key];
    return value is bool ? value : _bad(key);
  }

  bool booleanOr(String key, {required bool fallback}) {
    final value = _map[key];
    return value is bool ? value : fallback;
  }

  int integer(String key) {
    final value = _map[key];
    return value is int ? value : _bad(key);
  }

  int? integerOrNull(String key) {
    final value = _map[key];
    return value is int ? value : null;
  }

  double? doubleOrNull(String key) {
    final value = _map[key];
    return value is num ? value.toDouble() : null;
  }

  /// A timestamp; must carry an explicit offset (see `parseInstant`).
  DateTime instant(String key) => parseInstant(string(key));

  DateTime? instantOrNull(String key) {
    final value = _map[key];
    return value is String && value.isNotEmpty ? parseInstant(value) : null;
  }

  JsonReader? objectOrNull(String key) {
    final value = _map[key];
    return value is Map<String, Object?> ? JsonReader._(value, key) : null;
  }

  /// The raw nested value, for handing to a nested model's own `fromJson`.
  Object? raw(String key) => _map[key];

  /// A nested object parsed by [parse], or null when absent/null.
  T? optional<T>(String key, T Function(Object? json) parse) =>
      objectOrNull(key) == null ? null : parse(_map[key]);

  JsonReader object(String key) => objectOrNull(key) ?? _bad(key);

  List<T> list<T>(String key, T Function(Object? item) parse) {
    final value = _map[key];
    if (value is! List) return _bad(key);
    return List<T>.unmodifiable(value.map(parse));
  }

  List<T> listOrEmpty<T>(String key, T Function(Object? item) parse) {
    final value = _map[key];
    return value is List
        ? List<T>.unmodifiable(value.map(parse))
        : List<T>.empty();
  }
}
