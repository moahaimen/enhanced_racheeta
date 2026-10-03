// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appName => 'Racheeta';

  @override
  String get loading => 'Loading…';

  @override
  String get retry => 'Try again';

  @override
  String get cancel => 'Cancel';

  @override
  String get confirm => 'Confirm';

  @override
  String get fieldRequired => 'This field is required.';

  @override
  String get showPassword => 'Show password';

  @override
  String get hidePassword => 'Hide password';

  @override
  String get loginTitle => 'Sign in';

  @override
  String get loginIntro => 'Enter your email and password.';

  @override
  String get emailLabel => 'Email';

  @override
  String get passwordLabel => 'Password';

  @override
  String get loginButton => 'Sign in';

  @override
  String get loggingIn => 'Signing in…';

  @override
  String get sessionExpired =>
      'Your session has expired. Please sign in again.';

  @override
  String get errorNetwork =>
      'Could not reach the server. Check your connection and try again.';

  @override
  String get errorTimeout => 'The server took too long to respond. Try again.';

  @override
  String get errorInvalidCredentials => 'Incorrect email or password.';

  @override
  String get errorThrottled =>
      'Too many attempts. Wait a moment and try again.';

  @override
  String get errorForbidden => 'You are not allowed to do this.';

  @override
  String get errorServer =>
      'Something went wrong on our side. Try again later.';

  @override
  String get errorUnknown => 'Something went wrong. Try again.';

  @override
  String get restoringTitle => 'Restoring your session…';

  @override
  String get restoreFailedTitle => 'We couldn\'t verify your session';

  @override
  String get restoreFailedBody =>
      'The server could not be reached. You are still signed in on this device; try again.';

  @override
  String get restoreUseAnotherAccount => 'Use a different account';

  @override
  String get navHome => 'Home';

  @override
  String get navAccount => 'Account';

  @override
  String get navigationLabel => 'Main navigation';

  @override
  String homeGreeting(String name) {
    return 'Welcome, $name';
  }

  @override
  String homeSignedInAs(String role) {
    return 'Signed in as $role';
  }

  @override
  String get homeEmailNotVerified => 'Your email address is not verified yet.';

  @override
  String get accountTitle => 'Account';

  @override
  String get accountName => 'Name';

  @override
  String get accountEmail => 'Email';

  @override
  String get accountPhone => 'Phone';

  @override
  String get accountRole => 'Role';

  @override
  String get accountEmailStatus => 'Email status';

  @override
  String get accountEmailVerified => 'Verified';

  @override
  String get accountEmailNotVerified => 'Not verified';

  @override
  String get accountNotProvided => 'Not provided';

  @override
  String get accountLanguage => 'Language';

  @override
  String get languageArabic => 'العربية';

  @override
  String get languageEnglish => 'English';

  @override
  String get logout => 'Sign out';

  @override
  String get loggingOut => 'Signing out…';

  @override
  String get logoutConfirmTitle => 'Sign out?';

  @override
  String get logoutConfirmBody =>
      'You will need to sign in again to use Racheeta.';

  @override
  String get roleLabelPatient => 'Patient';

  @override
  String get roleLabelProvider => 'Healthcare provider';

  @override
  String get roleLabelMedicalCompany => 'Medical company / supplier';

  @override
  String get roleLabelRealEstateSeller => 'Medical real-estate owner or agent';

  @override
  String get roleLabelAdmin => 'Racheeta administrator';

  @override
  String get roleLabelUnknown => 'Account';

  @override
  String get configErrorTitle => 'The app is not configured';

  @override
  String get emptyTitle => 'Nothing here yet';
}
