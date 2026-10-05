import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ar.dart';
import 'app_localizations_en.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('ar'),
    Locale('en'),
  ];

  /// No description provided for @appName.
  ///
  /// In en, this message translates to:
  /// **'Racheeta'**
  String get appName;

  /// No description provided for @loading.
  ///
  /// In en, this message translates to:
  /// **'Loading…'**
  String get loading;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Try again'**
  String get retry;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @confirm.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get confirm;

  /// No description provided for @fieldRequired.
  ///
  /// In en, this message translates to:
  /// **'This field is required.'**
  String get fieldRequired;

  /// No description provided for @showPassword.
  ///
  /// In en, this message translates to:
  /// **'Show password'**
  String get showPassword;

  /// No description provided for @hidePassword.
  ///
  /// In en, this message translates to:
  /// **'Hide password'**
  String get hidePassword;

  /// No description provided for @loginTitle.
  ///
  /// In en, this message translates to:
  /// **'Sign in'**
  String get loginTitle;

  /// No description provided for @loginIntro.
  ///
  /// In en, this message translates to:
  /// **'Enter your email and password.'**
  String get loginIntro;

  /// No description provided for @emailLabel.
  ///
  /// In en, this message translates to:
  /// **'Email'**
  String get emailLabel;

  /// No description provided for @passwordLabel.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get passwordLabel;

  /// No description provided for @loginButton.
  ///
  /// In en, this message translates to:
  /// **'Sign in'**
  String get loginButton;

  /// No description provided for @loggingIn.
  ///
  /// In en, this message translates to:
  /// **'Signing in…'**
  String get loggingIn;

  /// No description provided for @sessionExpired.
  ///
  /// In en, this message translates to:
  /// **'Your session has expired. Please sign in again.'**
  String get sessionExpired;

  /// No description provided for @errorNetwork.
  ///
  /// In en, this message translates to:
  /// **'Could not reach the server. Check your connection and try again.'**
  String get errorNetwork;

  /// No description provided for @errorTimeout.
  ///
  /// In en, this message translates to:
  /// **'The server took too long to respond. Try again.'**
  String get errorTimeout;

  /// No description provided for @errorInvalidCredentials.
  ///
  /// In en, this message translates to:
  /// **'Incorrect email or password.'**
  String get errorInvalidCredentials;

  /// No description provided for @errorThrottled.
  ///
  /// In en, this message translates to:
  /// **'Too many attempts. Wait a moment and try again.'**
  String get errorThrottled;

  /// No description provided for @errorForbidden.
  ///
  /// In en, this message translates to:
  /// **'You are not allowed to do this.'**
  String get errorForbidden;

  /// No description provided for @errorServer.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong on our side. Try again later.'**
  String get errorServer;

  /// No description provided for @errorUnknown.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong. Try again.'**
  String get errorUnknown;

  /// No description provided for @restoringTitle.
  ///
  /// In en, this message translates to:
  /// **'Restoring your session…'**
  String get restoringTitle;

  /// No description provided for @restoreFailedTitle.
  ///
  /// In en, this message translates to:
  /// **'We couldn\'t verify your session'**
  String get restoreFailedTitle;

  /// No description provided for @restoreFailedBody.
  ///
  /// In en, this message translates to:
  /// **'The server could not be reached. You are still signed in on this device; try again.'**
  String get restoreFailedBody;

  /// No description provided for @restoreUseAnotherAccount.
  ///
  /// In en, this message translates to:
  /// **'Use a different account'**
  String get restoreUseAnotherAccount;

  /// No description provided for @navHome.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get navHome;

  /// No description provided for @navAccount.
  ///
  /// In en, this message translates to:
  /// **'Account'**
  String get navAccount;

  /// No description provided for @navigationLabel.
  ///
  /// In en, this message translates to:
  /// **'Main navigation'**
  String get navigationLabel;

  /// No description provided for @homeGreeting.
  ///
  /// In en, this message translates to:
  /// **'Welcome, {name}'**
  String homeGreeting(String name);

  /// No description provided for @homeSignedInAs.
  ///
  /// In en, this message translates to:
  /// **'Signed in as {role}'**
  String homeSignedInAs(String role);

  /// No description provided for @homeEmailNotVerified.
  ///
  /// In en, this message translates to:
  /// **'Your email address is not verified yet.'**
  String get homeEmailNotVerified;

  /// No description provided for @accountTitle.
  ///
  /// In en, this message translates to:
  /// **'Account'**
  String get accountTitle;

  /// No description provided for @accountName.
  ///
  /// In en, this message translates to:
  /// **'Name'**
  String get accountName;

  /// No description provided for @accountEmail.
  ///
  /// In en, this message translates to:
  /// **'Email'**
  String get accountEmail;

  /// No description provided for @accountPhone.
  ///
  /// In en, this message translates to:
  /// **'Phone'**
  String get accountPhone;

  /// No description provided for @accountRole.
  ///
  /// In en, this message translates to:
  /// **'Role'**
  String get accountRole;

  /// No description provided for @accountEmailStatus.
  ///
  /// In en, this message translates to:
  /// **'Email status'**
  String get accountEmailStatus;

  /// No description provided for @accountEmailVerified.
  ///
  /// In en, this message translates to:
  /// **'Verified'**
  String get accountEmailVerified;

  /// No description provided for @accountEmailNotVerified.
  ///
  /// In en, this message translates to:
  /// **'Not verified'**
  String get accountEmailNotVerified;

  /// No description provided for @accountNotProvided.
  ///
  /// In en, this message translates to:
  /// **'Not provided'**
  String get accountNotProvided;

  /// No description provided for @accountLanguage.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get accountLanguage;

  /// No description provided for @languageArabic.
  ///
  /// In en, this message translates to:
  /// **'العربية'**
  String get languageArabic;

  /// No description provided for @languageEnglish.
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get languageEnglish;

  /// No description provided for @logout.
  ///
  /// In en, this message translates to:
  /// **'Sign out'**
  String get logout;

  /// No description provided for @loggingOut.
  ///
  /// In en, this message translates to:
  /// **'Signing out…'**
  String get loggingOut;

  /// No description provided for @logoutConfirmTitle.
  ///
  /// In en, this message translates to:
  /// **'Sign out?'**
  String get logoutConfirmTitle;

  /// No description provided for @logoutConfirmBody.
  ///
  /// In en, this message translates to:
  /// **'You will need to sign in again to use Racheeta.'**
  String get logoutConfirmBody;

  /// No description provided for @roleLabelPatient.
  ///
  /// In en, this message translates to:
  /// **'Patient'**
  String get roleLabelPatient;

  /// No description provided for @roleLabelProvider.
  ///
  /// In en, this message translates to:
  /// **'Healthcare provider'**
  String get roleLabelProvider;

  /// No description provided for @roleLabelMedicalCompany.
  ///
  /// In en, this message translates to:
  /// **'Medical company / supplier'**
  String get roleLabelMedicalCompany;

  /// No description provided for @roleLabelRealEstateSeller.
  ///
  /// In en, this message translates to:
  /// **'Medical real-estate owner or agent'**
  String get roleLabelRealEstateSeller;

  /// No description provided for @roleLabelAdmin.
  ///
  /// In en, this message translates to:
  /// **'Racheeta administrator'**
  String get roleLabelAdmin;

  /// No description provided for @roleLabelUnknown.
  ///
  /// In en, this message translates to:
  /// **'Account'**
  String get roleLabelUnknown;

  /// No description provided for @configErrorTitle.
  ///
  /// In en, this message translates to:
  /// **'The app is not configured'**
  String get configErrorTitle;

  /// No description provided for @emptyTitle.
  ///
  /// In en, this message translates to:
  /// **'Nothing here yet'**
  String get emptyTitle;

  /// No description provided for @navDiscover.
  ///
  /// In en, this message translates to:
  /// **'Find care'**
  String get navDiscover;

  /// No description provided for @navReservations.
  ///
  /// In en, this message translates to:
  /// **'Appointments'**
  String get navReservations;

  /// No description provided for @discoverTitle.
  ///
  /// In en, this message translates to:
  /// **'Find a provider'**
  String get discoverTitle;

  /// No description provided for @searchHint.
  ///
  /// In en, this message translates to:
  /// **'Search by name'**
  String get searchHint;

  /// No description provided for @searchClear.
  ///
  /// In en, this message translates to:
  /// **'Clear search'**
  String get searchClear;

  /// No description provided for @filtersButton.
  ///
  /// In en, this message translates to:
  /// **'Filters'**
  String get filtersButton;

  /// No description provided for @filtersTitle.
  ///
  /// In en, this message translates to:
  /// **'Filter providers'**
  String get filtersTitle;

  /// No description provided for @filtersApply.
  ///
  /// In en, this message translates to:
  /// **'Apply'**
  String get filtersApply;

  /// No description provided for @filtersReset.
  ///
  /// In en, this message translates to:
  /// **'Reset'**
  String get filtersReset;

  /// No description provided for @filterKind.
  ///
  /// In en, this message translates to:
  /// **'Provider kind'**
  String get filterKind;

  /// No description provided for @kindPractitioner.
  ///
  /// In en, this message translates to:
  /// **'Practitioner'**
  String get kindPractitioner;

  /// No description provided for @kindFacility.
  ///
  /// In en, this message translates to:
  /// **'Facility'**
  String get kindFacility;

  /// No description provided for @filterType.
  ///
  /// In en, this message translates to:
  /// **'Type'**
  String get filterType;

  /// No description provided for @filterSpecialty.
  ///
  /// In en, this message translates to:
  /// **'Specialty'**
  String get filterSpecialty;

  /// No description provided for @filterGovernorate.
  ///
  /// In en, this message translates to:
  /// **'Governorate'**
  String get filterGovernorate;

  /// No description provided for @filterCity.
  ///
  /// In en, this message translates to:
  /// **'City'**
  String get filterCity;

  /// No description provided for @filterAny.
  ///
  /// In en, this message translates to:
  /// **'Any'**
  String get filterAny;

  /// No description provided for @filterLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Could not load the options.'**
  String get filterLoadFailed;

  /// No description provided for @sortLabel.
  ///
  /// In en, this message translates to:
  /// **'Sort by'**
  String get sortLabel;

  /// No description provided for @sortNameAsc.
  ///
  /// In en, this message translates to:
  /// **'Name (A–Z)'**
  String get sortNameAsc;

  /// No description provided for @sortNameDesc.
  ///
  /// In en, this message translates to:
  /// **'Name (Z–A)'**
  String get sortNameDesc;

  /// No description provided for @sortNewest.
  ///
  /// In en, this message translates to:
  /// **'Newest'**
  String get sortNewest;

  /// No description provided for @sortOldest.
  ///
  /// In en, this message translates to:
  /// **'Oldest'**
  String get sortOldest;

  /// No description provided for @providerTypeDoctor.
  ///
  /// In en, this message translates to:
  /// **'Doctor'**
  String get providerTypeDoctor;

  /// No description provided for @providerTypeNurse.
  ///
  /// In en, this message translates to:
  /// **'Nurse'**
  String get providerTypeNurse;

  /// No description provided for @providerTypeTherapist.
  ///
  /// In en, this message translates to:
  /// **'Therapist'**
  String get providerTypeTherapist;

  /// No description provided for @providerTypeHospital.
  ///
  /// In en, this message translates to:
  /// **'Hospital'**
  String get providerTypeHospital;

  /// No description provided for @providerTypeMedicalCenter.
  ///
  /// In en, this message translates to:
  /// **'Medical center'**
  String get providerTypeMedicalCenter;

  /// No description provided for @providerTypePharmacy.
  ///
  /// In en, this message translates to:
  /// **'Pharmacy'**
  String get providerTypePharmacy;

  /// No description provided for @providerTypeLaboratory.
  ///
  /// In en, this message translates to:
  /// **'Laboratory'**
  String get providerTypeLaboratory;

  /// No description provided for @providerTypeBeautyCenter.
  ///
  /// In en, this message translates to:
  /// **'Beauty center'**
  String get providerTypeBeautyCenter;

  /// No description provided for @discoverEmptyTitle.
  ///
  /// In en, this message translates to:
  /// **'No providers found'**
  String get discoverEmptyTitle;

  /// No description provided for @discoverEmptyBody.
  ///
  /// In en, this message translates to:
  /// **'Try changing your search or filters.'**
  String get discoverEmptyBody;

  /// No description provided for @clearFilters.
  ///
  /// In en, this message translates to:
  /// **'Clear filters'**
  String get clearFilters;

  /// No description provided for @resultsCount.
  ///
  /// In en, this message translates to:
  /// **'{count} results'**
  String resultsCount(int count);

  /// No description provided for @loadMore.
  ///
  /// In en, this message translates to:
  /// **'Load more'**
  String get loadMore;

  /// No description provided for @loadMoreFailed.
  ///
  /// In en, this message translates to:
  /// **'Could not load more results.'**
  String get loadMoreFailed;

  /// No description provided for @ratingSummary.
  ///
  /// In en, this message translates to:
  /// **'{rating} · {count} reviews'**
  String ratingSummary(String rating, int count);

  /// No description provided for @noReviews.
  ///
  /// In en, this message translates to:
  /// **'No reviews yet'**
  String get noReviews;

  /// No description provided for @verifiedSince.
  ///
  /// In en, this message translates to:
  /// **'Verified {date}'**
  String verifiedSince(String date);

  /// No description provided for @providerTitle.
  ///
  /// In en, this message translates to:
  /// **'Provider'**
  String get providerTitle;

  /// No description provided for @detailAbout.
  ///
  /// In en, this message translates to:
  /// **'About'**
  String get detailAbout;

  /// No description provided for @detailSpecialties.
  ///
  /// In en, this message translates to:
  /// **'Specialties'**
  String get detailSpecialties;

  /// No description provided for @detailLocation.
  ///
  /// In en, this message translates to:
  /// **'Location'**
  String get detailLocation;

  /// No description provided for @detailContact.
  ///
  /// In en, this message translates to:
  /// **'Contact'**
  String get detailContact;

  /// No description provided for @detailPhone.
  ///
  /// In en, this message translates to:
  /// **'Phone'**
  String get detailPhone;

  /// No description provided for @detailEmail.
  ///
  /// In en, this message translates to:
  /// **'Email'**
  String get detailEmail;

  /// No description provided for @detailWebsite.
  ///
  /// In en, this message translates to:
  /// **'Website'**
  String get detailWebsite;

  /// No description provided for @detailServices.
  ///
  /// In en, this message translates to:
  /// **'Services'**
  String get detailServices;

  /// No description provided for @noServices.
  ///
  /// In en, this message translates to:
  /// **'No services are listed.'**
  String get noServices;

  /// No description provided for @detailRelated.
  ///
  /// In en, this message translates to:
  /// **'Related providers'**
  String get detailRelated;

  /// No description provided for @serviceDuration.
  ///
  /// In en, this message translates to:
  /// **'{minutes} min'**
  String serviceDuration(int minutes);

  /// No description provided for @bookService.
  ///
  /// In en, this message translates to:
  /// **'Book'**
  String get bookService;

  /// No description provided for @bookingPatientsOnly.
  ///
  /// In en, this message translates to:
  /// **'Only patient accounts can book appointments.'**
  String get bookingPatientsOnly;

  /// No description provided for @bookingTitle.
  ///
  /// In en, this message translates to:
  /// **'Book an appointment'**
  String get bookingTitle;

  /// No description provided for @bookingChooseDay.
  ///
  /// In en, this message translates to:
  /// **'Choose a day'**
  String get bookingChooseDay;

  /// No description provided for @bookingChooseTime.
  ///
  /// In en, this message translates to:
  /// **'Choose a time'**
  String get bookingChooseTime;

  /// No description provided for @bookingNoSlots.
  ///
  /// In en, this message translates to:
  /// **'No appointments are available right now.'**
  String get bookingNoSlots;

  /// No description provided for @bookingNoSlotsHint.
  ///
  /// In en, this message translates to:
  /// **'Availability is set by the provider. Check again later.'**
  String get bookingNoSlotsHint;

  /// No description provided for @bookingRefresh.
  ///
  /// In en, this message translates to:
  /// **'Refresh availability'**
  String get bookingRefresh;

  /// No description provided for @bookingNote.
  ///
  /// In en, this message translates to:
  /// **'Note for the provider (optional)'**
  String get bookingNote;

  /// No description provided for @bookingNoteTooLong.
  ///
  /// In en, this message translates to:
  /// **'The note must be at most {max} characters.'**
  String bookingNoteTooLong(int max);

  /// No description provided for @bookingSummary.
  ///
  /// In en, this message translates to:
  /// **'Your appointment'**
  String get bookingSummary;

  /// No description provided for @bookingSelectSlot.
  ///
  /// In en, this message translates to:
  /// **'Select a time to continue.'**
  String get bookingSelectSlot;

  /// No description provided for @bookingTimezoneNote.
  ///
  /// In en, this message translates to:
  /// **'Times are shown in your device\'s time zone.'**
  String get bookingTimezoneNote;

  /// No description provided for @bookingConfirm.
  ///
  /// In en, this message translates to:
  /// **'Confirm booking'**
  String get bookingConfirm;

  /// No description provided for @bookingConfirming.
  ///
  /// In en, this message translates to:
  /// **'Booking…'**
  String get bookingConfirming;

  /// No description provided for @bookingSuccessTitle.
  ///
  /// In en, this message translates to:
  /// **'Booking sent'**
  String get bookingSuccessTitle;

  /// No description provided for @bookingSuccessBody.
  ///
  /// In en, this message translates to:
  /// **'You can follow its status under Appointments.'**
  String get bookingSuccessBody;

  /// No description provided for @bookingViewReservation.
  ///
  /// In en, this message translates to:
  /// **'View appointment'**
  String get bookingViewReservation;

  /// No description provided for @bookingSlotTaken.
  ///
  /// In en, this message translates to:
  /// **'That time is no longer available. The list has been refreshed; please pick another time.'**
  String get bookingSlotTaken;

  /// No description provided for @errorProviderUnavailable.
  ///
  /// In en, this message translates to:
  /// **'This provider is not accepting bookings right now.'**
  String get errorProviderUnavailable;

  /// No description provided for @errorServiceUnavailable.
  ///
  /// In en, this message translates to:
  /// **'This service is not available for booking right now.'**
  String get errorServiceUnavailable;

  /// No description provided for @errorNotFound.
  ///
  /// In en, this message translates to:
  /// **'We couldn\'t find that.'**
  String get errorNotFound;

  /// No description provided for @errorCannotCancel.
  ///
  /// In en, this message translates to:
  /// **'This appointment can no longer be cancelled.'**
  String get errorCannotCancel;

  /// No description provided for @reservationsTitle.
  ///
  /// In en, this message translates to:
  /// **'My appointments'**
  String get reservationsTitle;

  /// No description provided for @reservationsUpcoming.
  ///
  /// In en, this message translates to:
  /// **'Upcoming'**
  String get reservationsUpcoming;

  /// No description provided for @reservationsPast.
  ///
  /// In en, this message translates to:
  /// **'Past and closed'**
  String get reservationsPast;

  /// No description provided for @reservationsEmptyTitle.
  ///
  /// In en, this message translates to:
  /// **'No appointments yet'**
  String get reservationsEmptyTitle;

  /// No description provided for @reservationsEmptyBody.
  ///
  /// In en, this message translates to:
  /// **'When you book an appointment it will appear here.'**
  String get reservationsEmptyBody;

  /// No description provided for @reservationsFindCare.
  ///
  /// In en, this message translates to:
  /// **'Find a provider'**
  String get reservationsFindCare;

  /// No description provided for @reservationDetailTitle.
  ///
  /// In en, this message translates to:
  /// **'Appointment'**
  String get reservationDetailTitle;

  /// No description provided for @reservationProvider.
  ///
  /// In en, this message translates to:
  /// **'Provider'**
  String get reservationProvider;

  /// No description provided for @reservationService.
  ///
  /// In en, this message translates to:
  /// **'Service'**
  String get reservationService;

  /// No description provided for @reservationWhen.
  ///
  /// In en, this message translates to:
  /// **'Date and time'**
  String get reservationWhen;

  /// No description provided for @reservationDuration.
  ///
  /// In en, this message translates to:
  /// **'Duration'**
  String get reservationDuration;

  /// No description provided for @reservationPrice.
  ///
  /// In en, this message translates to:
  /// **'Price'**
  String get reservationPrice;

  /// No description provided for @reservationNote.
  ///
  /// In en, this message translates to:
  /// **'Your note'**
  String get reservationNote;

  /// No description provided for @reservationStatus.
  ///
  /// In en, this message translates to:
  /// **'Status'**
  String get reservationStatus;

  /// No description provided for @reservationHistory.
  ///
  /// In en, this message translates to:
  /// **'Status history'**
  String get reservationHistory;

  /// No description provided for @reservationViewProvider.
  ///
  /// In en, this message translates to:
  /// **'View provider'**
  String get reservationViewProvider;

  /// No description provided for @statusPending.
  ///
  /// In en, this message translates to:
  /// **'Pending'**
  String get statusPending;

  /// No description provided for @statusConfirmed.
  ///
  /// In en, this message translates to:
  /// **'Confirmed'**
  String get statusConfirmed;

  /// No description provided for @statusCompleted.
  ///
  /// In en, this message translates to:
  /// **'Completed'**
  String get statusCompleted;

  /// No description provided for @statusRejected.
  ///
  /// In en, this message translates to:
  /// **'Rejected'**
  String get statusRejected;

  /// No description provided for @statusCancelled.
  ///
  /// In en, this message translates to:
  /// **'Cancelled'**
  String get statusCancelled;

  /// No description provided for @statusNoShow.
  ///
  /// In en, this message translates to:
  /// **'No show'**
  String get statusNoShow;

  /// No description provided for @statusUnknown.
  ///
  /// In en, this message translates to:
  /// **'Unknown'**
  String get statusUnknown;

  /// No description provided for @cancelReservation.
  ///
  /// In en, this message translates to:
  /// **'Cancel appointment'**
  String get cancelReservation;

  /// No description provided for @cancellingReservation.
  ///
  /// In en, this message translates to:
  /// **'Cancelling…'**
  String get cancellingReservation;

  /// No description provided for @cancelConfirmTitle.
  ///
  /// In en, this message translates to:
  /// **'Cancel this appointment?'**
  String get cancelConfirmTitle;

  /// No description provided for @cancelConfirmBody.
  ///
  /// In en, this message translates to:
  /// **'This cannot be undone.'**
  String get cancelConfirmBody;

  /// No description provided for @cancelConfirmAction.
  ///
  /// In en, this message translates to:
  /// **'Cancel appointment'**
  String get cancelConfirmAction;

  /// No description provided for @cancelKeep.
  ///
  /// In en, this message translates to:
  /// **'Keep appointment'**
  String get cancelKeep;

  /// No description provided for @cancelSuccess.
  ///
  /// In en, this message translates to:
  /// **'The appointment was cancelled.'**
  String get cancelSuccess;

  /// No description provided for @navWorkspace.
  ///
  /// In en, this message translates to:
  /// **'Dashboard'**
  String get navWorkspace;

  /// No description provided for @navSchedule.
  ///
  /// In en, this message translates to:
  /// **'Availability'**
  String get navSchedule;

  /// No description provided for @navBookings.
  ///
  /// In en, this message translates to:
  /// **'Bookings'**
  String get navBookings;

  /// No description provided for @providerOnly.
  ///
  /// In en, this message translates to:
  /// **'This area is for provider accounts.'**
  String get providerOnly;

  /// No description provided for @providerProfileMissing.
  ///
  /// In en, this message translates to:
  /// **'Create your provider profile on the Racheeta website to use this area.'**
  String get providerProfileMissing;

  /// No description provided for @dashboardTitle.
  ///
  /// In en, this message translates to:
  /// **'Dashboard'**
  String get dashboardTitle;

  /// No description provided for @dashboardVerification.
  ///
  /// In en, this message translates to:
  /// **'Verification'**
  String get dashboardVerification;

  /// No description provided for @verificationUnverified.
  ///
  /// In en, this message translates to:
  /// **'Not verified'**
  String get verificationUnverified;

  /// No description provided for @verificationPending.
  ///
  /// In en, this message translates to:
  /// **'Pending review'**
  String get verificationPending;

  /// No description provided for @verificationVerified.
  ///
  /// In en, this message translates to:
  /// **'Verified'**
  String get verificationVerified;

  /// No description provided for @verificationRejected.
  ///
  /// In en, this message translates to:
  /// **'Rejected'**
  String get verificationRejected;

  /// No description provided for @verificationSuspended.
  ///
  /// In en, this message translates to:
  /// **'Suspended'**
  String get verificationSuspended;

  /// No description provided for @dashboardVisible.
  ///
  /// In en, this message translates to:
  /// **'Visible to patients'**
  String get dashboardVisible;

  /// No description provided for @dashboardHidden.
  ///
  /// In en, this message translates to:
  /// **'Not visible to patients'**
  String get dashboardHidden;

  /// No description provided for @dashboardReservations.
  ///
  /// In en, this message translates to:
  /// **'Reservations'**
  String get dashboardReservations;

  /// No description provided for @dashboardTotal.
  ///
  /// In en, this message translates to:
  /// **'Total'**
  String get dashboardTotal;

  /// No description provided for @dashboardUpcoming.
  ///
  /// In en, this message translates to:
  /// **'Upcoming'**
  String get dashboardUpcoming;

  /// No description provided for @dashboardUpcomingList.
  ///
  /// In en, this message translates to:
  /// **'Upcoming appointments'**
  String get dashboardUpcomingList;

  /// No description provided for @dashboardNoUpcoming.
  ///
  /// In en, this message translates to:
  /// **'No upcoming appointments.'**
  String get dashboardNoUpcoming;

  /// No description provided for @dashboardReviews.
  ///
  /// In en, this message translates to:
  /// **'Reviews'**
  String get dashboardReviews;

  /// No description provided for @dashboardOffers.
  ///
  /// In en, this message translates to:
  /// **'Offers'**
  String get dashboardOffers;

  /// No description provided for @offersTotal.
  ///
  /// In en, this message translates to:
  /// **'Total offers'**
  String get offersTotal;

  /// No description provided for @offersRunning.
  ///
  /// In en, this message translates to:
  /// **'Running now'**
  String get offersRunning;

  /// No description provided for @offersScheduled.
  ///
  /// In en, this message translates to:
  /// **'Scheduled'**
  String get offersScheduled;

  /// No description provided for @dashboardUnread.
  ///
  /// In en, this message translates to:
  /// **'Unread'**
  String get dashboardUnread;

  /// No description provided for @unreadNotifications.
  ///
  /// In en, this message translates to:
  /// **'Notifications'**
  String get unreadNotifications;

  /// No description provided for @unreadMessages.
  ///
  /// In en, this message translates to:
  /// **'Messages'**
  String get unreadMessages;

  /// No description provided for @dashboardPractitioners.
  ///
  /// In en, this message translates to:
  /// **'Practitioners'**
  String get dashboardPractitioners;

  /// No description provided for @practitionersActive.
  ///
  /// In en, this message translates to:
  /// **'Active'**
  String get practitionersActive;

  /// No description provided for @practitionersIncoming.
  ///
  /// In en, this message translates to:
  /// **'Incoming requests'**
  String get practitionersIncoming;

  /// No description provided for @practitionersOutgoing.
  ///
  /// In en, this message translates to:
  /// **'Outgoing invitations'**
  String get practitionersOutgoing;

  /// No description provided for @scheduleTitle.
  ///
  /// In en, this message translates to:
  /// **'Availability'**
  String get scheduleTitle;

  /// No description provided for @scheduleAdd.
  ///
  /// In en, this message translates to:
  /// **'Add availability'**
  String get scheduleAdd;

  /// No description provided for @scheduleEmptyTitle.
  ///
  /// In en, this message translates to:
  /// **'No upcoming availability'**
  String get scheduleEmptyTitle;

  /// No description provided for @scheduleEmptyBody.
  ///
  /// In en, this message translates to:
  /// **'Add the times patients can book.'**
  String get scheduleEmptyBody;

  /// No description provided for @scheduleNoneLoaded.
  ///
  /// In en, this message translates to:
  /// **'No upcoming times in the pages loaded so far.'**
  String get scheduleNoneLoaded;

  /// No description provided for @slotRemove.
  ///
  /// In en, this message translates to:
  /// **'Remove'**
  String get slotRemove;

  /// No description provided for @slotRemoving.
  ///
  /// In en, this message translates to:
  /// **'Removing…'**
  String get slotRemoving;

  /// No description provided for @slotRemoveConfirmTitle.
  ///
  /// In en, this message translates to:
  /// **'Remove this time?'**
  String get slotRemoveConfirmTitle;

  /// No description provided for @slotRemoveConfirmBody.
  ///
  /// In en, this message translates to:
  /// **'Patients will no longer be able to book it.'**
  String get slotRemoveConfirmBody;

  /// No description provided for @slotRemoveAction.
  ///
  /// In en, this message translates to:
  /// **'Remove'**
  String get slotRemoveAction;

  /// No description provided for @slotKeep.
  ///
  /// In en, this message translates to:
  /// **'Keep'**
  String get slotKeep;

  /// No description provided for @slotRemoved.
  ///
  /// In en, this message translates to:
  /// **'The time was removed.'**
  String get slotRemoved;

  /// No description provided for @slotCreated.
  ///
  /// In en, this message translates to:
  /// **'Availability added.'**
  String get slotCreated;

  /// No description provided for @slotFormTitle.
  ///
  /// In en, this message translates to:
  /// **'Add availability'**
  String get slotFormTitle;

  /// No description provided for @slotService.
  ///
  /// In en, this message translates to:
  /// **'Service'**
  String get slotService;

  /// No description provided for @slotPickDate.
  ///
  /// In en, this message translates to:
  /// **'Choose a date'**
  String get slotPickDate;

  /// No description provided for @slotPickTime.
  ///
  /// In en, this message translates to:
  /// **'Choose a start time'**
  String get slotPickTime;

  /// No description provided for @slotCreate.
  ///
  /// In en, this message translates to:
  /// **'Create availability'**
  String get slotCreate;

  /// No description provided for @slotCreating.
  ///
  /// In en, this message translates to:
  /// **'Adding…'**
  String get slotCreating;

  /// No description provided for @slotNoServices.
  ///
  /// In en, this message translates to:
  /// **'You need an active service with a duration before adding availability. Set one up on the Racheeta website.'**
  String get slotNoServices;

  /// No description provided for @slotSelectAll.
  ///
  /// In en, this message translates to:
  /// **'Choose a service, a date and a start time.'**
  String get slotSelectAll;

  /// No description provided for @slotBack.
  ///
  /// In en, this message translates to:
  /// **'Back to availability'**
  String get slotBack;

  /// No description provided for @errorSlotOverlap.
  ///
  /// In en, this message translates to:
  /// **'This time overlaps another active time.'**
  String get errorSlotOverlap;

  /// No description provided for @errorSlotPast.
  ///
  /// In en, this message translates to:
  /// **'The start time must be in the future.'**
  String get errorSlotPast;

  /// No description provided for @errorSlotService.
  ///
  /// In en, this message translates to:
  /// **'This service can\'t be used for availability. It must be active and have a duration.'**
  String get errorSlotService;

  /// No description provided for @errorSlotInUse.
  ///
  /// In en, this message translates to:
  /// **'A live booking uses this time, so it can\'t be removed.'**
  String get errorSlotInUse;

  /// No description provided for @bookingsTitle.
  ///
  /// In en, this message translates to:
  /// **'Bookings'**
  String get bookingsTitle;

  /// No description provided for @bookingsEmptyTitle.
  ///
  /// In en, this message translates to:
  /// **'No bookings yet'**
  String get bookingsEmptyTitle;

  /// No description provided for @bookingsEmptyBody.
  ///
  /// In en, this message translates to:
  /// **'Bookings from patients will appear here.'**
  String get bookingsEmptyBody;

  /// No description provided for @bookingDetailTitle.
  ///
  /// In en, this message translates to:
  /// **'Booking'**
  String get bookingDetailTitle;

  /// No description provided for @patientLabel.
  ///
  /// In en, this message translates to:
  /// **'Patient'**
  String get patientLabel;

  /// No description provided for @patientNoteLabel.
  ///
  /// In en, this message translates to:
  /// **'Patient\'s note'**
  String get patientNoteLabel;

  /// No description provided for @actionConfirm.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get actionConfirm;

  /// No description provided for @actionConfirming.
  ///
  /// In en, this message translates to:
  /// **'Confirming…'**
  String get actionConfirming;

  /// No description provided for @actionReject.
  ///
  /// In en, this message translates to:
  /// **'Reject'**
  String get actionReject;

  /// No description provided for @actionCancelBooking.
  ///
  /// In en, this message translates to:
  /// **'Cancel booking'**
  String get actionCancelBooking;

  /// No description provided for @actionComplete.
  ///
  /// In en, this message translates to:
  /// **'Mark as completed'**
  String get actionComplete;

  /// No description provided for @actionNoShow.
  ///
  /// In en, this message translates to:
  /// **'Mark as no-show'**
  String get actionNoShow;

  /// No description provided for @actionUpdating.
  ///
  /// In en, this message translates to:
  /// **'Updating…'**
  String get actionUpdating;

  /// No description provided for @confirmRejectTitle.
  ///
  /// In en, this message translates to:
  /// **'Reject this booking?'**
  String get confirmRejectTitle;

  /// No description provided for @confirmRejectBody.
  ///
  /// In en, this message translates to:
  /// **'The patient will see the new status. This cannot be undone.'**
  String get confirmRejectBody;

  /// No description provided for @confirmNoShowTitle.
  ///
  /// In en, this message translates to:
  /// **'Mark as no-show?'**
  String get confirmNoShowTitle;

  /// No description provided for @confirmNoShowBody.
  ///
  /// In en, this message translates to:
  /// **'The patient will see the new status. This cannot be undone.'**
  String get confirmNoShowBody;

  /// No description provided for @confirmCancelBookingTitle.
  ///
  /// In en, this message translates to:
  /// **'Cancel this booking?'**
  String get confirmCancelBookingTitle;

  /// No description provided for @confirmCancelBookingBody.
  ///
  /// In en, this message translates to:
  /// **'The patient will see the new status. This cannot be undone.'**
  String get confirmCancelBookingBody;

  /// No description provided for @confirmKeep.
  ///
  /// In en, this message translates to:
  /// **'Keep booking'**
  String get confirmKeep;

  /// No description provided for @transitionDone.
  ///
  /// In en, this message translates to:
  /// **'The booking was updated.'**
  String get transitionDone;

  /// No description provided for @errorTransitionRefused.
  ///
  /// In en, this message translates to:
  /// **'This booking can\'t be changed that way right now.'**
  String get errorTransitionRefused;

  /// No description provided for @searchGenericHint.
  ///
  /// In en, this message translates to:
  /// **'Search'**
  String get searchGenericHint;

  /// No description provided for @filtersGenericTitle.
  ///
  /// In en, this message translates to:
  /// **'Filters'**
  String get filtersGenericTitle;

  /// No description provided for @realEstateTitle.
  ///
  /// In en, this message translates to:
  /// **'Real estate'**
  String get realEstateTitle;

  /// No description provided for @realEstateSearchHint.
  ///
  /// In en, this message translates to:
  /// **'Search title, description or district'**
  String get realEstateSearchHint;

  /// No description provided for @realEstateFiltersTitle.
  ///
  /// In en, this message translates to:
  /// **'Filter properties'**
  String get realEstateFiltersTitle;

  /// No description provided for @filterTransaction.
  ///
  /// In en, this message translates to:
  /// **'Transaction'**
  String get filterTransaction;

  /// No description provided for @transactionSale.
  ///
  /// In en, this message translates to:
  /// **'For sale'**
  String get transactionSale;

  /// No description provided for @transactionRent.
  ///
  /// In en, this message translates to:
  /// **'For rent'**
  String get transactionRent;

  /// No description provided for @filterPropertyType.
  ///
  /// In en, this message translates to:
  /// **'Property type'**
  String get filterPropertyType;

  /// No description provided for @propertyClinic.
  ///
  /// In en, this message translates to:
  /// **'Clinic'**
  String get propertyClinic;

  /// No description provided for @propertyApartmentForClinic.
  ///
  /// In en, this message translates to:
  /// **'Apartment for a clinic'**
  String get propertyApartmentForClinic;

  /// No description provided for @propertyMedicalBuilding.
  ///
  /// In en, this message translates to:
  /// **'Medical building'**
  String get propertyMedicalBuilding;

  /// No description provided for @propertyPharmacyLocation.
  ///
  /// In en, this message translates to:
  /// **'Pharmacy location'**
  String get propertyPharmacyLocation;

  /// No description provided for @propertyLaboratoryLocation.
  ///
  /// In en, this message translates to:
  /// **'Laboratory location'**
  String get propertyLaboratoryLocation;

  /// No description provided for @propertyMedicalCenter.
  ///
  /// In en, this message translates to:
  /// **'Medical center'**
  String get propertyMedicalCenter;

  /// No description provided for @propertyHospitalBuilding.
  ///
  /// In en, this message translates to:
  /// **'Hospital building'**
  String get propertyHospitalBuilding;

  /// No description provided for @propertyCommercialMedical.
  ///
  /// In en, this message translates to:
  /// **'Commercial medical property'**
  String get propertyCommercialMedical;

  /// No description provided for @propertyInvestmentLand.
  ///
  /// In en, this message translates to:
  /// **'Medical investment land'**
  String get propertyInvestmentLand;

  /// No description provided for @sortPriceAsc.
  ///
  /// In en, this message translates to:
  /// **'Price: low to high'**
  String get sortPriceAsc;

  /// No description provided for @sortPriceDesc.
  ///
  /// In en, this message translates to:
  /// **'Price: high to low'**
  String get sortPriceDesc;

  /// No description provided for @realEstateEmptyTitle.
  ///
  /// In en, this message translates to:
  /// **'No properties found'**
  String get realEstateEmptyTitle;

  /// No description provided for @priceOnRequest.
  ///
  /// In en, this message translates to:
  /// **'Price on request'**
  String get priceOnRequest;

  /// No description provided for @areaLabel.
  ///
  /// In en, this message translates to:
  /// **'Area'**
  String get areaLabel;

  /// No description provided for @areaValue.
  ///
  /// In en, this message translates to:
  /// **'{area} m²'**
  String areaValue(String area);

  /// No description provided for @districtLabel.
  ///
  /// In en, this message translates to:
  /// **'District'**
  String get districtLabel;

  /// No description provided for @suitableForLabel.
  ///
  /// In en, this message translates to:
  /// **'Suitable for'**
  String get suitableForLabel;

  /// No description provided for @facilitiesLabel.
  ///
  /// In en, this message translates to:
  /// **'Facilities'**
  String get facilitiesLabel;

  /// No description provided for @listedByLabel.
  ///
  /// In en, this message translates to:
  /// **'Listed by'**
  String get listedByLabel;

  /// No description provided for @sellerOwner.
  ///
  /// In en, this message translates to:
  /// **'Owner'**
  String get sellerOwner;

  /// No description provided for @sellerAgent.
  ///
  /// In en, this message translates to:
  /// **'Agent'**
  String get sellerAgent;

  /// No description provided for @useClinic.
  ///
  /// In en, this message translates to:
  /// **'Clinic'**
  String get useClinic;

  /// No description provided for @usePharmacy.
  ///
  /// In en, this message translates to:
  /// **'Pharmacy'**
  String get usePharmacy;

  /// No description provided for @useLaboratory.
  ///
  /// In en, this message translates to:
  /// **'Laboratory'**
  String get useLaboratory;

  /// No description provided for @useMedicalCenter.
  ///
  /// In en, this message translates to:
  /// **'Medical center'**
  String get useMedicalCenter;

  /// No description provided for @useHospital.
  ///
  /// In en, this message translates to:
  /// **'Hospital'**
  String get useHospital;

  /// No description provided for @useGeneralMedical.
  ///
  /// In en, this message translates to:
  /// **'General medical use'**
  String get useGeneralMedical;

  /// No description provided for @useMedicalInvestment.
  ///
  /// In en, this message translates to:
  /// **'Medical investment'**
  String get useMedicalInvestment;

  /// No description provided for @listingDetailTitle.
  ///
  /// In en, this message translates to:
  /// **'Property'**
  String get listingDetailTitle;

  /// No description provided for @listingValidUntil.
  ///
  /// In en, this message translates to:
  /// **'Listing valid until'**
  String get listingValidUntil;

  /// No description provided for @sellerWorkspaceTitle.
  ///
  /// In en, this message translates to:
  /// **'Property owner'**
  String get sellerWorkspaceTitle;

  /// No description provided for @sellerOnly.
  ///
  /// In en, this message translates to:
  /// **'This area is for property-owner accounts.'**
  String get sellerOnly;

  /// No description provided for @sellerProfileMissing.
  ///
  /// In en, this message translates to:
  /// **'Create your seller profile on the Racheeta website to use this area.'**
  String get sellerProfileMissing;

  /// No description provided for @sellerListingsTotal.
  ///
  /// In en, this message translates to:
  /// **'Total listings'**
  String get sellerListingsTotal;

  /// No description provided for @sellerDraft.
  ///
  /// In en, this message translates to:
  /// **'Drafts'**
  String get sellerDraft;

  /// No description provided for @sellerPublished.
  ///
  /// In en, this message translates to:
  /// **'Published'**
  String get sellerPublished;

  /// No description provided for @sellerVisible.
  ///
  /// In en, this message translates to:
  /// **'Visible to the public'**
  String get sellerVisible;

  /// No description provided for @sellerExpired.
  ///
  /// In en, this message translates to:
  /// **'Expired'**
  String get sellerExpired;

  /// No description provided for @ownerListingsTitle.
  ///
  /// In en, this message translates to:
  /// **'My listings'**
  String get ownerListingsTitle;

  /// No description provided for @ownerListingsEmpty.
  ///
  /// In en, this message translates to:
  /// **'You have no listings yet'**
  String get ownerListingsEmpty;

  /// No description provided for @ownerListingsEmptyBody.
  ///
  /// In en, this message translates to:
  /// **'Create listings on the Racheeta website; you can publish them here.'**
  String get ownerListingsEmptyBody;

  /// No description provided for @ownerListingDetailTitle.
  ///
  /// In en, this message translates to:
  /// **'My listing'**
  String get ownerListingDetailTitle;

  /// No description provided for @statusDraft.
  ///
  /// In en, this message translates to:
  /// **'Draft'**
  String get statusDraft;

  /// No description provided for @statusPublished.
  ///
  /// In en, this message translates to:
  /// **'Published'**
  String get statusPublished;

  /// No description provided for @badgeVisible.
  ///
  /// In en, this message translates to:
  /// **'Visible'**
  String get badgeVisible;

  /// No description provided for @badgeNotVisible.
  ///
  /// In en, this message translates to:
  /// **'Not visible'**
  String get badgeNotVisible;

  /// No description provided for @badgeExpired.
  ///
  /// In en, this message translates to:
  /// **'Expired'**
  String get badgeExpired;

  /// No description provided for @listingPublish.
  ///
  /// In en, this message translates to:
  /// **'Publish'**
  String get listingPublish;

  /// No description provided for @listingPublishing.
  ///
  /// In en, this message translates to:
  /// **'Publishing…'**
  String get listingPublishing;

  /// No description provided for @listingUnpublish.
  ///
  /// In en, this message translates to:
  /// **'Unpublish'**
  String get listingUnpublish;

  /// No description provided for @listingUnpublishing.
  ///
  /// In en, this message translates to:
  /// **'Unpublishing…'**
  String get listingUnpublishing;

  /// No description provided for @confirmUnpublishTitle.
  ///
  /// In en, this message translates to:
  /// **'Unpublish this listing?'**
  String get confirmUnpublishTitle;

  /// No description provided for @confirmUnpublishBody.
  ///
  /// In en, this message translates to:
  /// **'It will no longer be visible to the public.'**
  String get confirmUnpublishBody;

  /// No description provided for @confirmKeepPublished.
  ///
  /// In en, this message translates to:
  /// **'Keep published'**
  String get confirmKeepPublished;

  /// No description provided for @listingPublished.
  ///
  /// In en, this message translates to:
  /// **'The listing was published.'**
  String get listingPublished;

  /// No description provided for @listingUnpublished.
  ///
  /// In en, this message translates to:
  /// **'The listing was unpublished.'**
  String get listingUnpublished;

  /// No description provided for @errorListingNotPublishable.
  ///
  /// In en, this message translates to:
  /// **'This listing can\'t be published yet. Complete it on the Racheeta website.'**
  String get errorListingNotPublishable;

  /// No description provided for @errorSellerNotEligible.
  ///
  /// In en, this message translates to:
  /// **'Your account can\'t manage listings right now.'**
  String get errorSellerNotEligible;

  /// No description provided for @exploreTitle.
  ///
  /// In en, this message translates to:
  /// **'Explore'**
  String get exploreTitle;

  /// No description provided for @errorListingTransition.
  ///
  /// In en, this message translates to:
  /// **'This listing can\'t be changed that way right now.'**
  String get errorListingTransition;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['ar', 'en'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ar':
      return AppLocalizationsAr();
    case 'en':
      return AppLocalizationsEn();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
