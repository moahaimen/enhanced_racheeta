import 'package:intl/intl.dart';

import '../../core/time/instants.dart';

/// Display formatting. Dates/times take an instant (UTC) and a [WallClock] converter so the time
/// zone policy is explicit at every call site (see `core/time/instants.dart`).
String formatDateTime(DateTime utc, WallClock wallClock, String locale) =>
    DateFormat.yMMMEd(locale).add_jm().format(wallClock(utc));

String formatDay(DateTime wallClockDay, String locale) =>
    DateFormat.MMMEd(locale).format(wallClockDay);

String formatTime(DateTime utc, WallClock wallClock, String locale) =>
    DateFormat.jm(locale).format(wallClock(utc));

String formatDate(DateTime utc, WallClock wallClock, String locale) =>
    DateFormat.yMMMd(locale).format(wallClock(utc));

/// `price` is the server's decimal string; shown grouped per locale, falling back to the raw text.
String formatMoney(String price, String currency, String locale) {
  final value = num.tryParse(price);
  final amount = value == null
      ? price
      : NumberFormat.decimalPattern(locale).format(value);
  return currency.isEmpty ? amount : '$amount $currency';
}

String formatRating(double rating, String locale) =>
    NumberFormat('0.0', locale).format(rating);
