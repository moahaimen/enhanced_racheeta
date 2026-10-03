// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Arabic (`ar`).
class AppLocalizationsAr extends AppLocalizations {
  AppLocalizationsAr([String locale = 'ar']) : super(locale);

  @override
  String get appName => 'رشيتة';

  @override
  String get loading => 'جارٍ التحميل…';

  @override
  String get retry => 'إعادة المحاولة';

  @override
  String get cancel => 'إلغاء';

  @override
  String get confirm => 'تأكيد';

  @override
  String get fieldRequired => 'هذا الحقل مطلوب.';

  @override
  String get showPassword => 'إظهار كلمة المرور';

  @override
  String get hidePassword => 'إخفاء كلمة المرور';

  @override
  String get loginTitle => 'تسجيل الدخول';

  @override
  String get loginIntro => 'أدخل بريدك الإلكتروني وكلمة المرور.';

  @override
  String get emailLabel => 'البريد الإلكتروني';

  @override
  String get passwordLabel => 'كلمة المرور';

  @override
  String get loginButton => 'دخول';

  @override
  String get loggingIn => 'جارٍ الدخول…';

  @override
  String get sessionExpired => 'انتهت جلستك. يرجى تسجيل الدخول مجدداً.';

  @override
  String get errorNetwork =>
      'تعذّر الاتصال بالخادم. تحقق من اتصالك وحاول مجدداً.';

  @override
  String get errorTimeout => 'استغرق الخادم وقتاً طويلاً في الرد. حاول مجدداً.';

  @override
  String get errorInvalidCredentials =>
      'البريد الإلكتروني أو كلمة المرور غير صحيحة.';

  @override
  String get errorThrottled => 'محاولات كثيرة. حاول مجدداً بعد قليل.';

  @override
  String get errorForbidden => 'غير مسموح لك بهذا الإجراء.';

  @override
  String get errorServer => 'حدث خطأ من جهتنا. حاول لاحقاً.';

  @override
  String get errorUnknown => 'حدث خطأ غير متوقع. حاول مجدداً.';

  @override
  String get restoringTitle => 'جارٍ استعادة جلستك…';

  @override
  String get restoreFailedTitle => 'تعذّر التحقق من جلستك';

  @override
  String get restoreFailedBody =>
      'تعذّر الاتصال بالخادم. ما زلت مسجّلاً الدخول على هذا الجهاز؛ حاول مجدداً.';

  @override
  String get restoreUseAnotherAccount => 'استخدام حساب آخر';

  @override
  String get navHome => 'الرئيسية';

  @override
  String get navAccount => 'حسابي';

  @override
  String get navigationLabel => 'التنقل الرئيسي';

  @override
  String homeGreeting(String name) {
    return 'مرحباً، $name';
  }

  @override
  String homeSignedInAs(String role) {
    return 'مسجّل الدخول بصفة $role';
  }

  @override
  String get homeEmailNotVerified => 'لم يتم تأكيد بريدك الإلكتروني بعد.';

  @override
  String get accountTitle => 'حسابي';

  @override
  String get accountName => 'الاسم';

  @override
  String get accountEmail => 'البريد الإلكتروني';

  @override
  String get accountPhone => 'الهاتف';

  @override
  String get accountRole => 'الدور';

  @override
  String get accountEmailStatus => 'حالة البريد';

  @override
  String get accountEmailVerified => 'مؤكَّد';

  @override
  String get accountEmailNotVerified => 'غير مؤكَّد';

  @override
  String get accountNotProvided => 'غير مُدخل';

  @override
  String get accountLanguage => 'اللغة';

  @override
  String get languageArabic => 'العربية';

  @override
  String get languageEnglish => 'English';

  @override
  String get logout => 'تسجيل الخروج';

  @override
  String get loggingOut => 'جارٍ الخروج…';

  @override
  String get logoutConfirmTitle => 'تسجيل الخروج؟';

  @override
  String get logoutConfirmBody =>
      'ستحتاج إلى تسجيل الدخول مجدداً لاستخدام رشيتة.';

  @override
  String get roleLabelPatient => 'مريض';

  @override
  String get roleLabelProvider => 'مقدّم خدمة صحية';

  @override
  String get roleLabelMedicalCompany => 'شركة طبية / مورّد';

  @override
  String get roleLabelRealEstateSeller => 'مالك أو وكيل عقارات طبية';

  @override
  String get roleLabelAdmin => 'مدير رشيتة';

  @override
  String get roleLabelUnknown => 'حساب';

  @override
  String get configErrorTitle => 'التطبيق غير مُهيّأ';

  @override
  String get emptyTitle => 'لا يوجد شيء هنا بعد';
}
