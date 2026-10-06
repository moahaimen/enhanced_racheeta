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

  @override
  String get navWorkspace => 'لوحة التحكم';

  @override
  String get navSchedule => 'المواعيد المتاحة';

  @override
  String get navBookings => 'الحجوزات';

  @override
  String get providerOnly => 'هذه المنطقة مخصصة لحسابات مقدمي الخدمة.';

  @override
  String get providerProfileMissing =>
      'أنشئ ملف مقدم الخدمة الخاص بك على موقع رشيتة لاستخدام هذه المنطقة.';

  @override
  String get dashboardTitle => 'لوحة التحكم';

  @override
  String get dashboardVerification => 'التوثيق';

  @override
  String get verificationUnverified => 'غير موثق';

  @override
  String get verificationPending => 'قيد المراجعة';

  @override
  String get verificationVerified => 'موثق';

  @override
  String get verificationRejected => 'مرفوض';

  @override
  String get verificationSuspended => 'موقوف';

  @override
  String get dashboardVisible => 'ظاهر للمرضى';

  @override
  String get dashboardHidden => 'غير ظاهر للمرضى';

  @override
  String get dashboardReservations => 'الحجوزات';

  @override
  String get dashboardTotal => 'الإجمالي';

  @override
  String get dashboardUpcoming => 'القادمة';

  @override
  String get dashboardUpcomingList => 'المواعيد القادمة';

  @override
  String get dashboardNoUpcoming => 'لا توجد مواعيد قادمة.';

  @override
  String get dashboardReviews => 'التقييمات';

  @override
  String get dashboardOffers => 'العروض';

  @override
  String get offersTotal => 'إجمالي العروض';

  @override
  String get offersRunning => 'سارية الآن';

  @override
  String get offersScheduled => 'مجدولة';

  @override
  String get dashboardUnread => 'غير المقروءة';

  @override
  String get unreadNotifications => 'الإشعارات';

  @override
  String get unreadMessages => 'الرسائل';

  @override
  String get dashboardPractitioners => 'الممارسون';

  @override
  String get practitionersActive => 'نشطون';

  @override
  String get practitionersIncoming => 'طلبات واردة';

  @override
  String get practitionersOutgoing => 'دعوات صادرة';

  @override
  String get scheduleTitle => 'المواعيد المتاحة';

  @override
  String get scheduleAdd => 'إضافة موعد متاح';

  @override
  String get scheduleEmptyTitle => 'لا توجد مواعيد متاحة قادمة';

  @override
  String get scheduleEmptyBody => 'أضف الأوقات التي يمكن للمرضى حجزها.';

  @override
  String get scheduleNoneLoaded =>
      'لا توجد مواعيد قادمة في الصفحات المحمّلة حتى الآن.';

  @override
  String get slotRemove => 'إزالة';

  @override
  String get slotRemoving => 'جارٍ الإزالة…';

  @override
  String get slotRemoveConfirmTitle => 'إزالة هذا الموعد؟';

  @override
  String get slotRemoveConfirmBody => 'لن يتمكن المرضى من حجزه بعد الآن.';

  @override
  String get slotRemoveAction => 'إزالة';

  @override
  String get slotKeep => 'إبقاء';

  @override
  String get slotRemoved => 'تمت إزالة الموعد.';

  @override
  String get slotCreated => 'تمت إضافة الموعد المتاح.';

  @override
  String get slotFormTitle => 'إضافة موعد متاح';

  @override
  String get slotService => 'الخدمة';

  @override
  String get slotPickDate => 'اختر التاريخ';

  @override
  String get slotPickTime => 'اختر وقت البدء';

  @override
  String get slotCreate => 'إنشاء الموعد';

  @override
  String get slotCreating => 'جارٍ الإضافة…';

  @override
  String get slotNoServices =>
      'تحتاج إلى خدمة نشطة ذات مدة قبل إضافة المواعيد. أنشئها على موقع رشيتة.';

  @override
  String get slotSelectAll => 'اختر الخدمة والتاريخ ووقت البدء.';

  @override
  String get slotBack => 'العودة إلى المواعيد المتاحة';

  @override
  String get errorSlotOverlap => 'يتداخل هذا الوقت مع موعد متاح آخر.';

  @override
  String get errorSlotPast => 'يجب أن يكون وقت البدء في المستقبل.';

  @override
  String get errorSlotService =>
      'لا يمكن استخدام هذه الخدمة للمواعيد. يجب أن تكون نشطة ولها مدة.';

  @override
  String get errorSlotInUse =>
      'هناك حجز قائم على هذا الموعد، لذلك لا يمكن إزالته.';

  @override
  String get bookingsTitle => 'الحجوزات';

  @override
  String get bookingsEmptyTitle => 'لا توجد حجوزات بعد';

  @override
  String get bookingsEmptyBody => 'ستظهر هنا حجوزات المرضى.';

  @override
  String get bookingDetailTitle => 'الحجز';

  @override
  String get patientLabel => 'المريض';

  @override
  String get patientNoteLabel => 'ملاحظة المريض';

  @override
  String get actionConfirm => 'تأكيد';

  @override
  String get actionConfirming => 'جارٍ التأكيد…';

  @override
  String get actionReject => 'رفض';

  @override
  String get actionCancelBooking => 'إلغاء الحجز';

  @override
  String get actionComplete => 'تحديد كمكتمل';

  @override
  String get actionNoShow => 'تحديد أنه لم يحضر';

  @override
  String get actionUpdating => 'جارٍ التحديث…';

  @override
  String get confirmRejectTitle => 'رفض هذا الحجز؟';

  @override
  String get confirmRejectBody =>
      'سيرى المريض الحالة الجديدة. لا يمكن التراجع عن ذلك.';

  @override
  String get confirmNoShowTitle => 'تحديد أنه لم يحضر؟';

  @override
  String get confirmNoShowBody =>
      'سيرى المريض الحالة الجديدة. لا يمكن التراجع عن ذلك.';

  @override
  String get confirmCancelBookingTitle => 'إلغاء هذا الحجز؟';

  @override
  String get confirmCancelBookingBody =>
      'سيرى المريض الحالة الجديدة. لا يمكن التراجع عن ذلك.';

  @override
  String get confirmKeep => 'إبقاء الحجز';

  @override
  String get transitionDone => 'تم تحديث الحجز.';

  @override
  String get errorTransitionRefused =>
      'لا يمكن تغيير هذا الحجز بهذه الطريقة الآن.';

  @override
  String get searchGenericHint => 'بحث';

  @override
  String get filtersGenericTitle => 'التصفية';

  @override
  String get realEstateTitle => 'العقارات';

  @override
  String get realEstateSearchHint => 'ابحث في العنوان أو الوصف أو الحي';

  @override
  String get realEstateFiltersTitle => 'تصفية العقارات';

  @override
  String get filterTransaction => 'نوع الصفقة';

  @override
  String get transactionSale => 'للبيع';

  @override
  String get transactionRent => 'للإيجار';

  @override
  String get filterPropertyType => 'نوع العقار';

  @override
  String get propertyClinic => 'عيادة';

  @override
  String get propertyApartmentForClinic => 'شقة لعيادة';

  @override
  String get propertyMedicalBuilding => 'مبنى طبي';

  @override
  String get propertyPharmacyLocation => 'موقع صيدلية';

  @override
  String get propertyLaboratoryLocation => 'موقع مختبر';

  @override
  String get propertyMedicalCenter => 'مركز طبي';

  @override
  String get propertyHospitalBuilding => 'مبنى مستشفى';

  @override
  String get propertyCommercialMedical => 'عقار تجاري طبي';

  @override
  String get propertyInvestmentLand => 'أرض استثمار طبي';

  @override
  String get sortPriceAsc => 'السعر: من الأقل';

  @override
  String get sortPriceDesc => 'السعر: من الأعلى';

  @override
  String get realEstateEmptyTitle => 'لا توجد عقارات';

  @override
  String get priceOnRequest => 'السعر عند الطلب';

  @override
  String get areaLabel => 'المساحة';

  @override
  String areaValue(String area) {
    return '$area م²';
  }

  @override
  String get districtLabel => 'الحي';

  @override
  String get suitableForLabel => 'مناسب لـ';

  @override
  String get facilitiesLabel => 'المرافق';

  @override
  String get listedByLabel => 'معروض من';

  @override
  String get sellerOwner => 'مالك';

  @override
  String get sellerAgent => 'وسيط';

  @override
  String get useClinic => 'عيادة';

  @override
  String get usePharmacy => 'صيدلية';

  @override
  String get useLaboratory => 'مختبر';

  @override
  String get useMedicalCenter => 'مركز طبي';

  @override
  String get useHospital => 'مستشفى';

  @override
  String get useGeneralMedical => 'استخدام طبي عام';

  @override
  String get useMedicalInvestment => 'استثمار طبي';

  @override
  String get listingDetailTitle => 'العقار';

  @override
  String get listingValidUntil => 'الإعلان ساري حتى';

  @override
  String get sellerWorkspaceTitle => 'مالك العقار';

  @override
  String get sellerOnly => 'هذه المنطقة مخصصة لحسابات مالكي العقارات.';

  @override
  String get sellerProfileMissing =>
      'أنشئ ملف البائع على موقع رشيتة لاستخدام هذه المنطقة.';

  @override
  String get sellerListingsTotal => 'إجمالي الإعلانات';

  @override
  String get sellerDraft => 'مسودات';

  @override
  String get sellerPublished => 'منشورة';

  @override
  String get sellerVisible => 'ظاهرة للعامة';

  @override
  String get sellerExpired => 'منتهية';

  @override
  String get ownerListingsTitle => 'إعلاناتي';

  @override
  String get ownerListingsEmpty => 'ليس لديك إعلانات بعد';

  @override
  String get ownerListingsEmptyBody =>
      'أنشئ الإعلانات على موقع رشيتة، ويمكنك نشرها من هنا.';

  @override
  String get ownerListingDetailTitle => 'إعلاني';

  @override
  String get statusDraft => 'مسودة';

  @override
  String get statusPublished => 'منشور';

  @override
  String get badgeVisible => 'ظاهر';

  @override
  String get badgeNotVisible => 'غير ظاهر';

  @override
  String get badgeExpired => 'منتهٍ';

  @override
  String get listingPublish => 'نشر';

  @override
  String get listingPublishing => 'جارٍ النشر…';

  @override
  String get listingUnpublish => 'إلغاء النشر';

  @override
  String get listingUnpublishing => 'جارٍ إلغاء النشر…';

  @override
  String get confirmUnpublishTitle => 'إلغاء نشر هذا الإعلان؟';

  @override
  String get confirmUnpublishBody => 'لن يكون ظاهراً للعامة بعد الآن.';

  @override
  String get confirmKeepPublished => 'إبقاؤه منشوراً';

  @override
  String get listingPublished => 'تم نشر الإعلان.';

  @override
  String get listingUnpublished => 'تم إلغاء نشر الإعلان.';

  @override
  String get errorListingNotPublishable =>
      'لا يمكن نشر هذا الإعلان بعد. أكمله على موقع رشيتة.';

  @override
  String get errorSellerNotEligible => 'لا يمكن لحسابك إدارة الإعلانات الآن.';

  @override
  String get exploreTitle => 'استكشف';

  @override
  String get errorListingTransition =>
      'لا يمكن تغيير هذا الإعلان بهذه الطريقة الآن.';

  @override
  String get marketplaceTitle => 'السوق الطبي';

  @override
  String get marketplaceFiltersTitle => 'تصفية المنتجات';

  @override
  String get marketplaceFilterCategory => 'الفئة';

  @override
  String get marketplaceEmptyTitle => 'لا توجد منتجات متاحة';

  @override
  String get marketplaceEmptyBody => 'تظهر المنتجات عندما تستهدف فئتها ملفك.';

  @override
  String get errorMarketplaceBrowse => 'يلزم ملف مقدم خدمة موثق لتصفح السوق.';

  @override
  String get productDetailTitle => 'المنتج';

  @override
  String get brandLabel => 'العلامة التجارية';

  @override
  String get modelLabel => 'الطراز';

  @override
  String get categoryLabel => 'الفئة';

  @override
  String get supplierLabel => 'المورّد';

  @override
  String get companyWorkspaceTitle => 'مساحة الشركة';

  @override
  String get companyOnly => 'هذه المنطقة مخصصة لحسابات الشركات الطبية.';

  @override
  String get companyProfileMissing =>
      'أنشئ ملف الشركة على موقع رشيتة لاستخدام هذه المنطقة.';

  @override
  String get companyCanPublish => 'يمكنك نشر المنتجات.';

  @override
  String get companyCannotPublish => 'النشر غير متاح حتى يتم توثيق شركتك.';

  @override
  String get productsTotal => 'إجمالي المنتجات';

  @override
  String get productsActive => 'فعالة';

  @override
  String get productsInactive => 'غير فعالة';

  @override
  String get productsExposable => 'ظاهرة لمقدمي الخدمة';

  @override
  String get companyProductsTitle => 'منتجاتي';

  @override
  String get companyProductsEmpty => 'ليس لديك منتجات بعد';

  @override
  String get companyProductsEmptyBody =>
      'أنشئ المنتجات على موقع رشيتة، ويمكنك تفعيلها من هنا.';

  @override
  String get companyProductDetailTitle => 'منتجي';

  @override
  String get productStatusActive => 'فعال';

  @override
  String get productStatusInactive => 'غير فعال';

  @override
  String get productActivate => 'تفعيل';

  @override
  String get productActivating => 'جارٍ التفعيل…';

  @override
  String get productDeactivate => 'إلغاء التفعيل';

  @override
  String get productDeactivating => 'جارٍ إلغاء التفعيل…';

  @override
  String get confirmDeactivateTitle => 'إلغاء تفعيل هذا المنتج؟';

  @override
  String get confirmDeactivateBody => 'لن يراه مقدمو الخدمة بعد الآن.';

  @override
  String get confirmKeepActive => 'إبقاؤه فعالاً';

  @override
  String get productActivated => 'تم تفعيل المنتج.';

  @override
  String get productDeactivated => 'تم إلغاء تفعيل المنتج.';

  @override
  String get errorCompanyNotVerified => 'يجب توثيق شركتك قبل تفعيل المنتجات.';

  @override
  String get errorCategoryUnavailable =>
      'لا يمكن استخدام فئة هذا المنتج للنشر الآن.';

  @override
  String get errorProductTransition =>
      'لا يمكن تغيير هذا المنتج بهذه الطريقة الآن.';

  @override
  String get professionDoctor => 'طبيب';

  @override
  String get professionDentist => 'طبيب أسنان';

  @override
  String get professionPharmacist => 'صيدلاني';

  @override
  String get professionNurse => 'ممرض';

  @override
  String get professionMidwife => 'قابلة';

  @override
  String get professionLabTechnician => 'فني مختبر';

  @override
  String get professionRadiologyTechnician => 'فني أشعة';

  @override
  String get professionAnesthesiaTechnician => 'فني تخدير';

  @override
  String get professionPhysiotherapist => 'أخصائي علاج طبيعي';

  @override
  String get professionNutritionist => 'أخصائي تغذية';

  @override
  String get professionPsychologist => 'أخصائي نفسي';

  @override
  String get professionMedicalAssistant => 'مساعد طبي';

  @override
  String get professionAdministrative => 'إداري';

  @override
  String get professionOther => 'أخرى';

  @override
  String get employmentFullTime => 'دوام كامل';

  @override
  String get employmentPartTime => 'دوام جزئي';

  @override
  String get employmentContract => 'عقد';

  @override
  String get employmentTemporary => 'مؤقت';

  @override
  String get employmentInternship => 'تدريب';

  @override
  String get employmentLocum => 'بديل مؤقت';

  @override
  String get workModeOnSite => 'في الموقع';

  @override
  String get workModeRemote => 'عن بُعد';

  @override
  String get workModeHybrid => 'هجين';

  @override
  String get shiftDay => 'نهاري';

  @override
  String get shiftNight => 'ليلي';

  @override
  String get shiftRotating => 'متناوب';

  @override
  String get shiftFlexible => 'مرن';

  @override
  String get shiftOnCall => 'استدعاء';

  @override
  String get degreeDiploma => 'دبلوم';

  @override
  String get degreeBachelor => 'بكالوريوس';

  @override
  String get degreeHigherDiploma => 'دبلوم عالٍ';

  @override
  String get degreeMaster => 'ماجستير';

  @override
  String get degreePhd => 'دكتوراه';

  @override
  String get degreeBoard => 'بورد';

  @override
  String get degreeOther => 'أخرى';

  @override
  String get jobStatusDraft => 'مسودة';

  @override
  String get jobStatusPendingAdminReview => 'قيد مراجعة الإدارة';

  @override
  String get jobStatusPublished => 'منشورة';

  @override
  String get jobStatusClosed => 'مغلقة';

  @override
  String get jobStatusExpired => 'منتهية';

  @override
  String get jobStatusRejected => 'مرفوضة';

  @override
  String get jobStatusSuspended => 'موقوفة';

  @override
  String get jobStatusArchived => 'مؤرشفة';

  @override
  String get applicationStatusSubmitted => 'مقدَّم';

  @override
  String get applicationStatusReviewing => 'قيد المراجعة';

  @override
  String get applicationStatusShortlisted => 'في القائمة المختصرة';

  @override
  String get applicationStatusInterview => 'مقابلة';

  @override
  String get applicationStatusAccepted => 'مقبول';

  @override
  String get applicationStatusRejected => 'مرفوض';

  @override
  String get applicationStatusWithdrawn => 'مسحوب';

  @override
  String get jobsTitle => 'الوظائف';

  @override
  String get jobsSearchHint => 'ابحث عن وظيفة';

  @override
  String get jobsFiltersTitle => 'تصفية الوظائف';

  @override
  String get filterProfession => 'المهنة';

  @override
  String get filterEmploymentType => 'نوع التوظيف';

  @override
  String get filterWorkMode => 'نمط العمل';

  @override
  String get jobsEmptyTitle => 'لا توجد وظائف';

  @override
  String get jobDetailTitle => 'الوظيفة';

  @override
  String get jobEmployerLabel => 'جهة العمل';

  @override
  String jobOnBehalfOf(String name) {
    return 'نيابةً عن $name';
  }

  @override
  String get jobSalaryLabel => 'الراتب';

  @override
  String jobSalaryRange(String min, String max, String currency) {
    return '$min – $max $currency';
  }

  @override
  String jobSalaryFrom(String min, String currency) {
    return 'من $min $currency';
  }

  @override
  String jobSalaryUpTo(String max, String currency) {
    return 'حتى $max $currency';
  }

  @override
  String get jobDeadlineLabel => 'آخر موعد للتقديم';

  @override
  String get jobOpeningsLabel => 'عدد الشواغر';

  @override
  String get jobExperienceLabel => 'الخبرة الدنيا';

  @override
  String jobExperienceYears(int years) {
    return '$years سنوات';
  }

  @override
  String get jobDegreeLabel => 'الشهادة الدنيا';

  @override
  String get jobShiftLabel => 'الدوام';

  @override
  String get jobSpecialtyLabel => 'التخصص';

  @override
  String get jobResponsibilitiesLabel => 'المسؤوليات';

  @override
  String get jobRequirementsLabel => 'المتطلبات';

  @override
  String get jobWorkplaceLabel => 'مكان العمل';

  @override
  String get jobFeaturedBadge => 'مميزة';

  @override
  String get jobClosedNotice => 'هذه الوظيفة غير مفتوحة للتقديم.';

  @override
  String get applyTitle => 'قدّم على هذه الوظيفة';

  @override
  String get applyCoverText => 'رسالة تقديم (اختيارية)';

  @override
  String applyCoverTooLong(int max) {
    return 'يجب ألا تتجاوز الرسالة $max حرفاً.';
  }

  @override
  String get applyAction => 'إرسال الطلب';

  @override
  String get applyPending => 'جارٍ الإرسال…';

  @override
  String get applySent => 'تم إرسال طلبك.';

  @override
  String get applyViewMine => 'عرض طلباتي';

  @override
  String get errorProfileRequired => 'أنشئ ملفك المهني على موقع رشيتة للتقديم.';

  @override
  String get errorJobNotOpen => 'لم تعد هذه الوظيفة مفتوحة للتقديم.';

  @override
  String get errorDeadlinePassed => 'انتهى الموعد النهائي للتقديم.';

  @override
  String get errorAlreadyApplied => 'لقد قدّمت على هذه الوظيفة من قبل.';

  @override
  String get errorContactNotAllowed =>
      'أزل أرقام الهاتف والبريد الإلكتروني والروابط من الرسالة.';

  @override
  String get errorApplicationLimit => 'خطتك لا تسمح بالمزيد من الطلبات حالياً.';

  @override
  String get myApplicationsTitle => 'طلباتي';

  @override
  String get myApplicationsEmpty => 'لم تقدّم على أي وظيفة بعد';

  @override
  String get myApplicationsEmptyBody => 'تظهر هنا الطلبات التي ترسلها.';

  @override
  String applicationSubmittedOn(String date) {
    return 'أُرسل في $date';
  }

  @override
  String get applicationWithdraw => 'سحب الطلب';

  @override
  String get applicationWithdrawing => 'جارٍ سحب الطلب…';

  @override
  String get confirmWithdrawTitle => 'سحب هذا الطلب؟';

  @override
  String get confirmWithdrawBody =>
      'ستراه جهة العمل كطلب مسحوب. لا يمكن التراجع عن ذلك.';

  @override
  String get confirmKeepApplication => 'إبقاء الطلب';

  @override
  String get applicationWithdrawn => 'تم سحب الطلب.';

  @override
  String get errorApplicationTransition =>
      'لا يمكن تغيير هذا الطلب بهذه الطريقة الآن.';

  @override
  String get recruiterWorkspaceTitle => 'مساحة التوظيف';

  @override
  String get recruiterOnly => 'هذه المنطقة مخصصة لأعضاء جهات التوظيف.';

  @override
  String get recruiterProfileMissing => 'لست عضواً في جهة توظيف.';

  @override
  String get recruiterOrganization => 'الجهة';

  @override
  String get recruiterMyRole => 'دوري';

  @override
  String get recruiterRecruitmentStatus => 'التوظيف';

  @override
  String get recruiterCanRecruit => 'يمكن لهذه الجهة التوظيف.';

  @override
  String get recruiterCannotRecruit => 'لا يمكن لهذه الجهة التوظيف الآن.';

  @override
  String get recruiterJobsHeading => 'الوظائف';

  @override
  String get recruiterOpenNow => 'مفتوحة الآن';

  @override
  String get recruiterApplicationsHeading => 'الطلبات';

  @override
  String get recruiterAwaitingReview => 'بانتظار المراجعة';

  @override
  String get recruiterLast7Days => 'آخر 7 أيام';

  @override
  String get recruiterApplicationsWithheld =>
      'أرقام الطلبات غير متاحة لهذا الحساب.';

  @override
  String get recruiterInterviewsHeading => 'المقابلات';

  @override
  String get recruiterSeatsHeading => 'المقاعد';

  @override
  String get recruiterSeatsActive => 'الأعضاء النشطون';

  @override
  String get recruiterSeatsLimit => 'الحد الأقصى';

  @override
  String get recruiterOpenJobs => 'وظائف الجهة';

  @override
  String get recruiterJobsTitle => 'وظائف الجهة';

  @override
  String get recruiterJobsEmpty => 'لا توجد وظائف بعد';

  @override
  String get recruiterJobsEmptyBody =>
      'أنشئ الوظائف على موقع رشيتة، ويمكنك متابعتها وإغلاقها من هنا.';

  @override
  String get recruiterJobDetailTitle => 'وظيفة الجهة';

  @override
  String get recruiterApplicationsCount => 'الطلبات المستلمة';

  @override
  String get filterJobStatus => 'الحالة';

  @override
  String get jobClose => 'إغلاق الوظيفة';

  @override
  String get jobClosing => 'جارٍ الإغلاق…';

  @override
  String get confirmCloseJobTitle => 'إغلاق هذه الوظيفة؟';

  @override
  String get confirmCloseJobBody => 'ستتوقف عن استقبال الطلبات.';

  @override
  String get confirmKeepJob => 'إبقاؤها مفتوحة';

  @override
  String get jobClosedDone => 'تم إغلاق الوظيفة.';

  @override
  String get errorMembershipInactive => 'عضويتك لم تعد تسمح بهذا الإجراء.';

  @override
  String get errorJobTransition =>
      'لا يمكن تغيير هذه الوظيفة بهذه الطريقة الآن.';

  @override
  String get notificationsTitle => 'الإشعارات';

  @override
  String get notificationsEmpty => 'لا توجد إشعارات بعد';

  @override
  String get notificationsEmptyBody => 'تظهر هنا التحديثات الخاصة بحجوزاتك.';

  @override
  String get notificationsMarkAll => 'تحديد الكل كمقروء';

  @override
  String get notificationsMarkingAll => 'جارٍ التحديد…';

  @override
  String notificationsAllMarked(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'تم تحديد $count إشعارات كمقروءة.',
      one: 'تم تحديد إشعار واحد كمقروء.',
      zero: 'لا شيء لتحديده.',
    );
    return '$_temp0';
  }

  @override
  String notificationsUnreadCount(int count) {
    return '$count غير مقروء';
  }

  @override
  String get notificationUnread => 'غير مقروء';

  @override
  String get notificationRead => 'مقروء';

  @override
  String get notificationFallbackTitle => 'إشعار';

  @override
  String get errorNotificationMark => 'تعذّر تحديث الإشعار. حاول مجدداً.';

  @override
  String get pushPromptTitle => 'تفعيل الإشعارات الفورية';

  @override
  String get pushPromptBody =>
      'اسمح بالإشعارات ليصلك تنبيه عند حدوث جديد. وتبقى كل التفاصيل هنا حتى بدونها.';

  @override
  String get pushPromptAction => 'السماح بالإشعارات';

  @override
  String get pushDeniedHint =>
      'الإشعارات الفورية متوقفة لهذا التطبيق. يمكنك تفعيلها من إعدادات النظام، وتبقى كل التفاصيل ظاهرة هنا.';

  @override
  String get chatTitle => 'الرسائل';

  @override
  String get conversationTitle => 'محادثة';

  @override
  String get chatEmpty => 'لا توجد محادثات بعد';

  @override
  String get chatEmptyBody =>
      'تظهر هنا المحادثات الخاصة بحجوزاتك بعد بدء إحداها.';

  @override
  String get chatContextReservation => 'محادثة حجز';

  @override
  String get chatContextOther => 'محادثة';

  @override
  String get chatNoMessages => 'لا توجد رسائل بعد. ابدأ بالتحية.';

  @override
  String get chatLoadOlder => 'تحميل رسائل أقدم';

  @override
  String get chatLoadOlderFailed => 'تعذّر تحميل الرسائل الأقدم.';

  @override
  String get chatComposerLabel => 'الرسالة';

  @override
  String get chatSend => 'إرسال';

  @override
  String get chatSending => 'جارٍ الإرسال…';

  @override
  String get chatErrorBlank => 'اكتب رسالة أولاً.';

  @override
  String chatErrorTooLong(int max) {
    return 'يمكن أن تصل الرسالة إلى $max حرفاً كحد أقصى.';
  }

  @override
  String get chatErrorSend => 'لم تُرسل رسالتك. حاول مجدداً.';

  @override
  String get chatYou => 'أنت';

  @override
  String chatUnread(int count) {
    return '$count غير مقروءة';
  }

  @override
  String get chatMessageProvider => 'مراسلة مقدّم الخدمة';

  @override
  String get chatMessagePatient => 'مراسلة المريض';

  @override
  String get chatOpening => 'جارٍ الفتح…';

  @override
  String get chatOpenFailed => 'تعذّر فتح المحادثة.';
}
