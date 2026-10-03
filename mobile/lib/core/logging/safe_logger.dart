import 'package:flutter/foundation.dart';

/// Minimal logger that cannot leak credentials or personal data.
///
/// Rules: only log *metadata* (method, path, status, duration, error class). Never log request or
/// response bodies, headers, tokens, e-mail addresses or names. As a second line of defence every
/// message is passed through [redact], and nothing is printed in release builds.
class SafeLogger {
  const SafeLogger({this.enabled = kDebugMode, this._sink});

  final bool enabled;
  final void Function(String line)? _sink;

  static final _bearer = RegExp(
    r'Bearer\s+[A-Za-z0-9\-._~+/]+=*',
    caseSensitive: false,
  );
  static final _jwt = RegExp(
    r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*',
  );
  static final _email = RegExp(
    r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
  );
  static final _secretPair = RegExp(
    r'''("?(?:access|refresh|token|password|authorization)"?\s*[:=]\s*)("[^"]*"|[^\s,}&]+)''',
    caseSensitive: false,
  );

  /// Removes anything that looks like a credential or an e-mail address.
  static String redact(String input) => input
      .replaceAll(_bearer, 'Bearer [redacted]')
      .replaceAll(_jwt, '[redacted-jwt]')
      .replaceAllMapped(_secretPair, (m) => '${m[1]}[redacted]')
      .replaceAll(_email, '[redacted-email]');

  void info(String message) => _write('INFO', message);
  void warning(String message) => _write('WARN', message);

  void _write(String level, String message) {
    if (!enabled) return;
    final line = '[racheeta] $level ${redact(message)}';
    final sink = _sink;
    if (sink != null) {
      sink(line);
    } else {
      debugPrint(line);
    }
  }
}
