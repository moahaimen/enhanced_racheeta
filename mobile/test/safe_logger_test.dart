import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/core/logging/safe_logger.dart';

void main() {
  group('SafeLogger.redact', () {
    test('removes bearer tokens, JWTs, secrets in key/value form and e-mail addresses', () {
      const jwt = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl';
      final line = SafeLogger.redact(
        'Authorization: Bearer abc.def-ghi; token=$jwt; "refresh": "secret-refresh-value"; '
        'password=hunter2 user layla@example.com',
      );
      for (final secret in [
        'abc.def-ghi',
        jwt,
        'secret-refresh-value',
        'hunter2',
        'layla@example.com',
      ]) {
        expect(line, isNot(contains(secret)));
      }
    });

    test('leaves ordinary metadata readable', () {
      expect(
        SafeLogger.redact('GET /api/v1/me -> 200 (12ms)'),
        'GET /api/v1/me -> 200 (12ms)',
      );
    });
  });

  test('writes nothing when disabled and passes redacted lines to the sink when enabled', () {
    final lines = <String>[];
    const SafeLogger(enabled: false).info('x');
    SafeLogger(sink: lines.add).warning('refresh=abc123');
    expect(lines, hasLength(1));
    expect(lines.single, isNot(contains('abc123')));
  });
}
