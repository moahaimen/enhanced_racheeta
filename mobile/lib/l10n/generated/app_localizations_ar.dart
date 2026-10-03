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

  @override
  String get navDiscover => 'البحث عن رعاية';

  @override
  String get navReservations => 'مواعيدي';

  @override
  String get discoverTitle => 'ابحث عن مقدم رعاية';

  @override
  String get searchHint => 'ابحث بالاسم';

  @override
  String get searchClear => 'مسح البحث';

  @override
  String get filtersButton => 'تصفية';

  @override
  String get filtersTitle => 'تصفية مقدمي الرعاية';

  @override
  String get filtersApply => 'تطبيق';

  @override
  String get filtersReset => 'إعادة ضبط';

  @override
  String get filterKind => 'فئة مقدم الرعاية';

  @override
  String get kindPractitioner => 'ممارس';

  @override
  String get kindFacility => 'منشأة';

  @override
  String get filterType => 'النوع';

  @override
  String get filterSpecialty => 'التخصص';

  @override
  String get filterGovernorate => 'المحافظة';

  @override
  String get filterCity => 'المدينة';

  @override
  String get filterAny => 'الكل';

  @override
  String get filterLoadFailed => 'تعذّر تحميل الخيارات.';

  @override
  String get sortLabel => 'ترتيب حسب';

  @override
  String get sortNameAsc => 'الاسم (أ–ي)';

  @override
  String get sortNameDesc => 'الاسم (ي–أ)';

  @override
  String get sortNewest => 'الأحدث';

  @override
  String get sortOldest => 'الأقدم';

  @override
  String get providerTypeDoctor => 'طبيب';

  @override
  String get providerTypeNurse => 'ممرض';

  @override
  String get providerTypeTherapist => 'معالج';

  @override
  String get providerTypeHospital => 'مستشفى';

  @override
  String get providerTypeMedicalCenter => 'مركز طبي';

  @override
  String get providerTypePharmacy => 'صيدلية';

  @override
  String get providerTypeLaboratory => 'مختبر';

  @override
  String get providerTypeBeautyCenter => 'مركز تجميل';

  @override
  String get discoverEmptyTitle => 'لم يتم العثور على مقدمي رعاية';

  @override
  String get discoverEmptyBody => 'جرّب تغيير البحث أو عوامل التصفية.';

  @override
  String get clearFilters => 'مسح عوامل التصفية';

  @override
  String resultsCount(int count) {
    return '$count نتيجة';
  }

  @override
  String get loadMore => 'عرض المزيد';

  @override
  String get loadMoreFailed => 'تعذّر تحميل المزيد من النتائج.';

  @override
  String ratingSummary(String rating, int count) {
    return '$rating · $count تقييم';
  }

  @override
  String get noReviews => 'لا توجد تقييمات بعد';

  @override
  String verifiedSince(String date) {
    return 'موثّق منذ $date';
  }

  @override
  String get providerTitle => 'مقدم الرعاية';

  @override
  String get detailAbout => 'نبذة';

  @override
  String get detailSpecialties => 'التخصصات';

  @override
  String get detailLocation => 'الموقع';

  @override
  String get detailContact => 'التواصل';

  @override
  String get detailPhone => 'الهاتف';

  @override
  String get detailEmail => 'البريد الإلكتروني';

  @override
  String get detailWebsite => 'الموقع الإلكتروني';

  @override
  String get detailServices => 'الخدمات';

  @override
  String get noServices => 'لا توجد خدمات مدرجة.';

  @override
  String get detailRelated => 'مقدمو رعاية مرتبطون';

  @override
  String serviceDuration(int minutes) {
    return '$minutes دقيقة';
  }

  @override
  String get bookService => 'احجز';

  @override
  String get bookingPatientsOnly => 'الحجز متاح لحسابات المرضى فقط.';

  @override
  String get bookingTitle => 'حجز موعد';

  @override
  String get bookingChooseDay => 'اختر اليوم';

  @override
  String get bookingChooseTime => 'اختر الوقت';

  @override
  String get bookingNoSlots => 'لا توجد مواعيد متاحة حالياً.';

  @override
  String get bookingNoSlotsHint =>
      'يحدد مقدم الرعاية المواعيد المتاحة. حاول مرة أخرى لاحقاً.';

  @override
  String get bookingRefresh => 'تحديث المواعيد';

  @override
  String get bookingNote => 'ملاحظة لمقدم الرعاية (اختياري)';

  @override
  String bookingNoteTooLong(int max) {
    return 'يجب ألا تتجاوز الملاحظة $max حرفاً.';
  }

  @override
  String get bookingSummary => 'موعدك';

  @override
  String get bookingSelectSlot => 'اختر وقتاً للمتابعة.';

  @override
  String get bookingTimezoneNote => 'تُعرض الأوقات حسب المنطقة الزمنية لجهازك.';

  @override
  String get bookingConfirm => 'تأكيد الحجز';

  @override
  String get bookingConfirming => 'جارٍ الحجز…';

  @override
  String get bookingSuccessTitle => 'تم إرسال الحجز';

  @override
  String get bookingSuccessBody => 'يمكنك متابعة حالته من قسم المواعيد.';

  @override
  String get bookingViewReservation => 'عرض الموعد';

  @override
  String get bookingSlotTaken =>
      'لم يعد هذا الوقت متاحاً. تم تحديث القائمة، يرجى اختيار وقت آخر.';

  @override
  String get errorProviderUnavailable =>
      'لا يقبل مقدم الرعاية الحجوزات حالياً.';

  @override
  String get errorServiceUnavailable => 'هذه الخدمة غير متاحة للحجز حالياً.';

  @override
  String get errorNotFound => 'لم نعثر على ما تبحث عنه.';

  @override
  String get errorCannotCancel => 'لا يمكن إلغاء هذا الموعد بعد الآن.';

  @override
  String get reservationsTitle => 'مواعيدي';

  @override
  String get reservationsUpcoming => 'القادمة';

  @override
  String get reservationsPast => 'السابقة والمغلقة';

  @override
  String get reservationsEmptyTitle => 'لا توجد مواعيد بعد';

  @override
  String get reservationsEmptyBody => 'عند حجز موعد سيظهر هنا.';

  @override
  String get reservationsFindCare => 'ابحث عن مقدم رعاية';

  @override
  String get reservationDetailTitle => 'الموعد';

  @override
  String get reservationProvider => 'مقدم الرعاية';

  @override
  String get reservationService => 'الخدمة';

  @override
  String get reservationWhen => 'التاريخ والوقت';

  @override
  String get reservationDuration => 'المدة';

  @override
  String get reservationPrice => 'السعر';

  @override
  String get reservationNote => 'ملاحظتك';

  @override
  String get reservationStatus => 'الحالة';

  @override
  String get reservationHistory => 'سجل الحالة';

  @override
  String get reservationViewProvider => 'عرض مقدم الرعاية';

  @override
  String get statusPending => 'قيد الانتظار';

  @override
  String get statusConfirmed => 'مؤكد';

  @override
  String get statusCompleted => 'مكتمل';

  @override
  String get statusRejected => 'مرفوض';

  @override
  String get statusCancelled => 'ملغى';

  @override
  String get statusNoShow => 'لم يحضر';

  @override
  String get statusUnknown => 'غير معروف';

  @override
  String get cancelReservation => 'إلغاء الموعد';

  @override
  String get cancellingReservation => 'جارٍ الإلغاء…';

  @override
  String get cancelConfirmTitle => 'إلغاء هذا الموعد؟';

  @override
  String get cancelConfirmBody => 'لا يمكن التراجع عن هذا الإجراء.';

  @override
  String get cancelConfirmAction => 'إلغاء الموعد';

  @override
  String get cancelKeep => 'الإبقاء على الموعد';

  @override
  String get cancelSuccess => 'تم إلغاء الموعد.';
}
