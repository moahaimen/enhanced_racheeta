/// Timezone policy (docs/RESERVATIONS.md "Mobile"): the backend stores and returns UTC instants
/// (`USE_TZ=True`, `TIME_ZONE=UTC`) and has no provider timezone field. The app therefore
///
/// * accepts only timestamps that carry an explicit offset (`Z` or `±hh:mm`); an offset-less
///   string would be silently read as *local* time by `DateTime.parse`, so it is rejected;
/// * keeps every instant as UTC internally and sends UTC to the API;
/// * converts to the **device's** local time only for display (`toWallClock`), including the
///   calendar day used to group appointment slots, and converts a date/time the user *picked* back
///   to UTC (`deviceLocalToUtc`) before sending it.
library;

final RegExp _hasOffset = RegExp(
  r'(Z|[+-]\d{2}(:?\d{2})?)$',
  caseSensitive: false,
);

/// Parses an ISO-8601 timestamp with an explicit offset into a UTC [DateTime].
DateTime parseInstant(String text) {
  if (!_hasOffset.hasMatch(text) || !text.contains('T')) {
    throw FormatException('Timestamp without an explicit offset: "$text".');
  }
  return DateTime.parse(text).toUtc();
}

/// The wire form for query parameters: always UTC, `Z`-suffixed.
String toWireInstant(DateTime instant) => instant.toUtc().toIso8601String();

/// Converts a UTC instant to the wall-clock time shown to the user (device local time).
typedef WallClock = DateTime Function(DateTime utc);

DateTime deviceWallClock(DateTime utc) => utc.toUtc().toLocal();

/// The inverse of [WallClock]: the UTC instant of a wall-clock date and time the user picked in the
/// device's time zone (used when a provider chooses when an appointment slot starts).
typedef LocalToUtc = DateTime Function(DateTime wallClock);

DateTime deviceLocalToUtc(DateTime wallClock) => DateTime(
  wallClock.year,
  wallClock.month,
  wallClock.day,
  wallClock.hour,
  wallClock.minute,
).toUtc();

/// A calendar day (no time) used to group slots by the user's local day.
DateTime dayOf(DateTime wallClock) =>
    DateTime(wallClock.year, wallClock.month, wallClock.day);

final RegExp _calendarDate = RegExp(r'^\d{4}-\d{2}-\d{2}$');

/// A backend DATE (`YYYY-MM-DD`, e.g. a job application deadline): a calendar day with no time and
/// no zone. It is NOT an instant, so it is shown as the same calendar day everywhere and is never
/// converted between zones. Anything else is rejected rather than guessed.
DateTime parseCalendarDate(String text) {
  if (!_calendarDate.hasMatch(text)) {
    throw FormatException('Not a calendar date: "$text".');
  }
  final parsed = DateTime.parse(text);
  // `DateTime.parse` accepts month 13 style input by normalising; re-check the round trip.
  if (parsed.toIso8601String().substring(0, 10) != text) {
    throw FormatException('Not a calendar date: "$text".');
  }
  return DateTime(parsed.year, parsed.month, parsed.day);
}
