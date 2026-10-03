import 'package:shared_preferences/shared_preferences.dart';

/// Non-sensitive user preferences (currently only the UI language).
/// Credentials never go here; see [TokenStore].
abstract interface class PreferencesStore {
  String? readLanguageCode();
  Future<void> writeLanguageCode(String code);
}

class SharedPreferencesStore implements PreferencesStore {
  SharedPreferencesStore(this._prefs);
  static const _languageKey = 'racheeta.pref.language';
  final SharedPreferences _prefs;

  @override
  String? readLanguageCode() => _prefs.getString(_languageKey);

  @override
  Future<void> writeLanguageCode(String code) =>
      _prefs.setString(_languageKey, code);
}

class MemoryPreferencesStore implements PreferencesStore {
  MemoryPreferencesStore([this._language]);
  String? _language;

  @override
  String? readLanguageCode() => _language;

  @override
  Future<void> writeLanguageCode(String code) async => _language = code;
}
