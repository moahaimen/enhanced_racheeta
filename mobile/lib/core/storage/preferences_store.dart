import 'package:shared_preferences/shared_preferences.dart';

/// Non-sensitive user preferences (the UI language and the push-ownership sequence counter).
/// Credentials never go here; see [TokenStore].
abstract interface class PreferencesStore {
  String? readLanguageCode();
  Future<void> writeLanguageCode(String code);

  /// The last push-ownership sequence handed out on this installation (null: none yet). It is an
  /// opaque ordering number, not sensitive, and deliberately NOT cleared on logout or an account
  /// switch: ordering must stay monotonic across accounts and restarts.
  int? readPushOwnershipSeq();
  Future<void> writePushOwnershipSeq(int value);
}

class SharedPreferencesStore implements PreferencesStore {
  SharedPreferencesStore(this._prefs);
  static const _languageKey = 'racheeta.pref.language';
  static const _ownershipSeqKey = 'racheeta.push_ownership_seq';
  final SharedPreferences _prefs;

  @override
  String? readLanguageCode() => _prefs.getString(_languageKey);

  @override
  Future<void> writeLanguageCode(String code) =>
      _prefs.setString(_languageKey, code);

  @override
  int? readPushOwnershipSeq() => _prefs.getInt(_ownershipSeqKey);

  @override
  Future<void> writePushOwnershipSeq(int value) =>
      _prefs.setInt(_ownershipSeqKey, value);
}

class MemoryPreferencesStore implements PreferencesStore {
  MemoryPreferencesStore([this._language, this._ownershipSeq]);
  String? _language;
  int? _ownershipSeq;

  @override
  String? readLanguageCode() => _language;

  @override
  Future<void> writeLanguageCode(String code) async => _language = code;

  @override
  int? readPushOwnershipSeq() => _ownershipSeq;

  @override
  Future<void> writePushOwnershipSeq(int value) async => _ownershipSeq = value;
}
