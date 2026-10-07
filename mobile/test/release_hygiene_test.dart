import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/core/logging/safe_logger.dart';

/// Release hygiene guards: source and configuration invariants that must never regress.
/// (Tests run from `mobile/`.)
List<File> _dartFiles(String dir) =>
    Directory(dir)
        .listSync(recursive: true)
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'))
        .toList();

String _read(String path) => File(path).readAsStringSync();

void main() {
  group('logging and privacy', () {
    test(
      'release builds are silent by default (logging follows kDebugMode)',
      () {
        expect(const SafeLogger().enabled, kDebugMode);
        const SafeLogger(enabled: false).info('never printed');
      },
    );

    test('the only code that prints is SafeLogger itself', () {
      final offenders = <String>[];
      for (final file in _dartFiles('lib')) {
        if (file.path.endsWith('core/logging/safe_logger.dart')) continue;
        final source = file.readAsStringSync();
        for (final pattern in [
          RegExp(r'(^|[^\w.])print\('),
          RegExp(r'debugPrint\('),
          RegExp(r'developer\.log\('),
          RegExp(r'\bstdout\b'),
          RegExp(r'\bstderr\b'),
          RegExp(r"import 'dart:developer'"),
        ]) {
          if (pattern.hasMatch(source)) offenders.add('${file.path}: $pattern');
        }
      }
      expect(offenders, isEmpty);
    });

    test('no log call interpolates a token, password, e-mail, message body or payload', () {
      final call = RegExp(
        r'(logger|_logger)\s*\.(info|warning)\(([^;]*?)\);',
        dotAll: true,
      );
      final forbidden = RegExp(
        r'(token|password|bearer|email|phone|\.body|\.data\b|payload|cover|draft|message\.)',
        caseSensitive: false,
      );
      final offenders = <String>[];
      for (final file in _dartFiles('lib')) {
        for (final match in call.allMatches(file.readAsStringSync())) {
          final arguments = match.group(3)!;
          // the interpolated parts only: ${...} and $name
          final interpolations = RegExp(r'\$\{[^}]*\}|\$\w+')
              .allMatches(arguments);
          for (final part in interpolations) {
            if (forbidden.hasMatch(part.group(0)!)) {
              offenders.add('${file.path}: ${part.group(0)}');
            }
          }
        }
      }
      expect(offenders, isEmpty);
    });

    test(
      'redaction still removes credentials from anything that does get logged',
      () {
        final lines = <String>[];
        SafeLogger(sink: lines.add).info(
          'Bearer abc.def.ghi token=fcm-secret password: hunter2 a@b.example',
        );
        final out = lines.single;
        expect(out, isNot(contains('fcm-secret')));
        expect(out, isNot(contains('hunter2')));
        expect(out, isNot(contains('a@b.example')));
      },
    );
  });

  group('network configuration in source', () {
    test('no http:// URL is hard-coded in the app except the development fallback and its deny-list', () {
      final offenders = <String>[];
      for (final file in _dartFiles('lib')) {
        if (file.path.contains('lib/l10n/')) continue;
        for (final line in file.readAsLinesSync()) {
          if (line.contains('http://') &&
              !file.path.endsWith('app_config.dart')) {
            offenders.add('${file.path}: $line');
          }
        }
      }
      expect(offenders, isEmpty);
    });

    test('the development fallback is guarded by the compile-time release constant', () {
      final source = _read('lib/core/config/app_config.dart');
      expect(source, contains('!kReleaseMode &&'));
    });

    test('the app opens no external URL and has no web view', () {
      for (final file in _dartFiles('lib')) {
        final source = file.readAsStringSync();
        expect(source, isNot(contains('url_launcher')), reason: file.path);
        expect(source, isNot(contains('webview')), reason: file.path);
        expect(source, isNot(contains('launchUrl')), reason: file.path);
      }
      final pubspec = _read('pubspec.yaml');
      expect(pubspec, isNot(contains('url_launcher')));
      expect(pubspec, isNot(contains('webview')));
    });
  });

  group('dependencies', () {
    test('every direct dependency is pinned to an exact version', () {
      final section = RegExp(
        r'^dependencies:\n((?:  .*\n)+)',
        multiLine: true,
      ).firstMatch(_read('pubspec.yaml'))!.group(1)!;
      for (final line in section.split('\n')) {
        final match = RegExp(r'^  (\w+): (.+)$').firstMatch(line);
        if (match == null) continue; // `flutter:` / `sdk: flutter` sub-keys
        final version = match.group(2)!.trim();
        expect(version, matches(RegExp(r'^\d+\.\d+\.\d+$')), reason: line);
      }
    });
  });

  group('lifecycle', () {
    test('every stream subscription is cancelled and every timer / controller disposed', () {
      final offenders = <String>[];
      for (final file in _dartFiles('lib')) {
        final source = file.readAsStringSync();
        final resources = <String, RegExp>{
          'Timer': RegExp(r'\bTimer(\.periodic)?\('),
          'TextEditingController': RegExp(r'TextEditingController\('),
          'ScrollController': RegExp(r'ScrollController\('),
          'FocusNode': RegExp(r'FocusNode\('),
          'Stream.listen': RegExp(r'\.(listen)\(\s*\n?\s*\(?[\w, ]*\)?\s*=>'),
        };
        for (final entry in resources.entries) {
          if (!entry.value.hasMatch(source)) continue;
          final released = switch (entry.key) {
            'Timer' =>
              source.contains('.cancel()') || source.contains('?.cancel()'),
            'Stream.listen' => source.contains('cancel'),
            _ => source.contains('.dispose()'),
          };
          if (!released) offenders.add('${file.path}: ${entry.key}');
        }
      }
      expect(offenders, isEmpty);
    });
  });

  group('Android release configuration', () {
    final manifest = _read('android/app/src/main/AndroidManifest.xml');
    final gradle = _read('android/app/build.gradle.kts');

    test(
      'the main manifest carries the network permission and the audited policy',
      () {
        expect(manifest, contains('android.permission.INTERNET'));
        expect(manifest, contains('android:allowBackup="false"'));
        expect(manifest, contains('android:usesCleartextTraffic="false"'));
        expect(manifest, contains('android:dataExtractionRules='));
        expect(manifest, isNot(contains('android:debuggable')));
      },
    );

    test('no permission beyond internet and notifications is declared by the app itself', () {
      final declared = RegExp(r'<uses-permission android:name="([^"]+)"')
          .allMatches(manifest)
          .map((m) => m.group(1)!)
          .toSet();
      expect(declared, {
        'android.permission.INTERNET',
        'android.permission.POST_NOTIFICATIONS',
      });
    });

    test('only the launcher activity is exported by the app', () {
      expect(
        RegExp(r'android:exported="true"').allMatches(manifest),
        hasLength(1),
      );
      expect(manifest, isNot(contains('<service')));
      expect(manifest, isNot(contains('<receiver')));
      expect(manifest, isNot(contains('<provider')));
    });

    test('the debug manifest may allow cleartext, the main and profile manifests may not', () {
      expect(
        _read('android/app/src/debug/AndroidManifest.xml'),
        contains('usesCleartextTraffic="true"'),
      );
      expect(
        _read('android/app/src/profile/AndroidManifest.xml'),
        isNot(contains('usesCleartextTraffic="true"')),
      );
    });

    test(
      'release signing is fail-closed and no secret is in the repository',
      () {
        expect(gradle, contains('racheetaAllowDebugSignedRelease'));
        expect(gradle, contains('Release signing is not configured'));
        expect(
          gradle,
          isNot(
            contains('signingConfig = signingConfigs.getByName("debug")\n'),
          ),
        );
        expect(gradle, isNot(RegExp(r'storePassword\s*=\s*"[^"$]')));
        expect(gradle, isNot(RegExp(r'keyPassword\s*=\s*"[^"$]')));
        expect(gradle, contains('isMinifyEnabled = true'));
        expect(gradle, contains('isShrinkResources = true'));
        final example = _read('android/key.properties.example');
        expect(example, contains('CHANGE_ME'));
        final stray = Directory('android')
            .listSync(recursive: true)
            .whereType<File>()
            .where(
              (f) =>
                  RegExp(r'\.(jks|keystore|p12)$').hasMatch(f.path) ||
                  f.path.endsWith('/key.properties'),
            )
            .map((f) => f.path)
            .toList();
        expect(
          stray,
          isEmpty,
          reason: 'signing material must stay outside the repository',
        );
      },
    );

    test('no Firebase client or server credential file is part of the app', () {
      expect(File('android/app/google-services.json').existsSync(), isFalse);
      expect(File('ios/Runner/GoogleService-Info.plist').existsSync(), isFalse);
    });
  });
}
