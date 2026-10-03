import 'package:flutter/foundation.dart';

/// `{access, refresh}` from login and refresh (`TokenPair`/`Refresh` in docs/api/openapi.yaml).
/// The string form never contains the tokens.
@immutable
class TokenPair {
  const TokenPair({required this.access, required this.refresh});

  factory TokenPair.fromJson(Object? json) {
    if (json is Map<String, Object?> &&
        json['access'] is String &&
        json['refresh'] is String) {
      final access = json['access']! as String;
      final refresh = json['refresh']! as String;
      if (access.isNotEmpty && refresh.isNotEmpty) {
        return TokenPair(access: access, refresh: refresh);
      }
    }
    throw const FormatException('Malformed token response.');
  }

  final String access;
  final String refresh;

  @override
  String toString() => 'TokenPair(<redacted>)';
}

/// Primary role (`AccountRoleEnum`). Unknown future values are preserved, never dropped.
enum AccountRole {
  patient('PATIENT'),
  provider('PROVIDER'),
  medicalCompany('MEDICAL_COMPANY'),
  realEstateSeller('REAL_ESTATE_SELLER'),
  admin('ADMIN');

  const AccountRole(this.wire);
  final String wire;

  static AccountRole? tryParse(String value) {
    for (final role in values) {
      if (role.wire == value) return role;
    }
    return null;
  }
}

/// `GET /api/v1/me` (`Account` in the OpenAPI contract): the ONLY source of identity, role and
/// permissions. Capability codes (`permissions`) are informational for showing/hiding UI; the
/// backend re-checks every action. Nothing here is persisted on the device.
@immutable
class Account {
  const Account({
    required this.id,
    required this.email,
    required this.fullName,
    required this.phoneNumber,
    required this.roleCode,
    required this.preferredLanguage,
    required this.emailVerified,
    required this.hasPassword,
    required this.isStaff,
    required this.permissions,
  });

  factory Account.fromJson(Object? json) {
    if (json is! Map<String, Object?>) {
      throw const FormatException('Malformed account.');
    }
    String text(String key) {
      final value = json[key];
      if (value is String) return value;
      throw FormatException('Missing account field "$key".');
    }

    final permissions = json['permissions'];
    return Account(
      id: text('id'),
      email: text('email'),
      fullName: text('full_name'),
      phoneNumber: (json['phone_number'] as String?) ?? '',
      roleCode: text('role'),
      preferredLanguage: (json['preferred_language'] as String?) ?? 'ar',
      emailVerified: json['email_verified'] == true,
      hasPassword: json['has_password'] != false,
      isStaff: json['is_staff'] == true,
      permissions: permissions is List
          ? Set<String>.unmodifiable(permissions.whereType<String>())
          : const <String>{},
    );
  }

  final String id;
  final String email;
  final String fullName;
  final String phoneNumber;

  /// Raw backend role code (always present, even for roles this build does not know).
  final String roleCode;
  final String preferredLanguage;
  final bool emailVerified;
  final bool hasPassword;
  final bool isStaff;
  final Set<String> permissions;

  AccountRole? get role => AccountRole.tryParse(roleCode);

  /// Capability codes are authoritative-from-the-server hints; the backend still enforces.
  bool hasPermission(String code) => permissions.contains(code);

  @override
  String toString() => 'Account($roleCode)'; // no personal data in logs
}
