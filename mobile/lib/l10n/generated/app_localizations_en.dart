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

  @override
  String get navDiscover => 'Find care';

  @override
  String get navReservations => 'Appointments';

  @override
  String get discoverTitle => 'Find a provider';

  @override
  String get searchHint => 'Search by name';

  @override
  String get searchClear => 'Clear search';

  @override
  String get filtersButton => 'Filters';

  @override
  String get filtersTitle => 'Filter providers';

  @override
  String get filtersApply => 'Apply';

  @override
  String get filtersReset => 'Reset';

  @override
  String get filterKind => 'Provider kind';

  @override
  String get kindPractitioner => 'Practitioner';

  @override
  String get kindFacility => 'Facility';

  @override
  String get filterType => 'Type';

  @override
  String get filterSpecialty => 'Specialty';

  @override
  String get filterGovernorate => 'Governorate';

  @override
  String get filterCity => 'City';

  @override
  String get filterAny => 'Any';

  @override
  String get filterLoadFailed => 'Could not load the options.';

  @override
  String get sortLabel => 'Sort by';

  @override
  String get sortNameAsc => 'Name (A–Z)';

  @override
  String get sortNameDesc => 'Name (Z–A)';

  @override
  String get sortNewest => 'Newest';

  @override
  String get sortOldest => 'Oldest';

  @override
  String get providerTypeDoctor => 'Doctor';

  @override
  String get providerTypeNurse => 'Nurse';

  @override
  String get providerTypeTherapist => 'Therapist';

  @override
  String get providerTypeHospital => 'Hospital';

  @override
  String get providerTypeMedicalCenter => 'Medical center';

  @override
  String get providerTypePharmacy => 'Pharmacy';

  @override
  String get providerTypeLaboratory => 'Laboratory';

  @override
  String get providerTypeBeautyCenter => 'Beauty center';

  @override
  String get discoverEmptyTitle => 'No providers found';

  @override
  String get discoverEmptyBody => 'Try changing your search or filters.';

  @override
  String get clearFilters => 'Clear filters';

  @override
  String resultsCount(int count) {
    return '$count results';
  }

  @override
  String get loadMore => 'Load more';

  @override
  String get loadMoreFailed => 'Could not load more results.';

  @override
  String ratingSummary(String rating, int count) {
    return '$rating · $count reviews';
  }

  @override
  String get noReviews => 'No reviews yet';

  @override
  String verifiedSince(String date) {
    return 'Verified $date';
  }

  @override
  String get providerTitle => 'Provider';

  @override
  String get detailAbout => 'About';

  @override
  String get detailSpecialties => 'Specialties';

  @override
  String get detailLocation => 'Location';

  @override
  String get detailContact => 'Contact';

  @override
  String get detailPhone => 'Phone';

  @override
  String get detailEmail => 'Email';

  @override
  String get detailWebsite => 'Website';

  @override
  String get detailServices => 'Services';

  @override
  String get noServices => 'No services are listed.';

  @override
  String get detailRelated => 'Related providers';

  @override
  String serviceDuration(int minutes) {
    return '$minutes min';
  }

  @override
  String get bookService => 'Book';

  @override
  String get bookingPatientsOnly =>
      'Only patient accounts can book appointments.';

  @override
  String get bookingTitle => 'Book an appointment';

  @override
  String get bookingChooseDay => 'Choose a day';

  @override
  String get bookingChooseTime => 'Choose a time';

  @override
  String get bookingNoSlots => 'No appointments are available right now.';

  @override
  String get bookingNoSlotsHint =>
      'Availability is set by the provider. Check again later.';

  @override
  String get bookingRefresh => 'Refresh availability';

  @override
  String get bookingNote => 'Note for the provider (optional)';

  @override
  String bookingNoteTooLong(int max) {
    return 'The note must be at most $max characters.';
  }

  @override
  String get bookingSummary => 'Your appointment';

  @override
  String get bookingSelectSlot => 'Select a time to continue.';

  @override
  String get bookingTimezoneNote =>
      'Times are shown in your device\'s time zone.';

  @override
  String get bookingConfirm => 'Confirm booking';

  @override
  String get bookingConfirming => 'Booking…';

  @override
  String get bookingSuccessTitle => 'Booking sent';

  @override
  String get bookingSuccessBody =>
      'You can follow its status under Appointments.';

  @override
  String get bookingViewReservation => 'View appointment';

  @override
  String get bookingSlotTaken =>
      'That time is no longer available. The list has been refreshed; please pick another time.';

  @override
  String get errorProviderUnavailable =>
      'This provider is not accepting bookings right now.';

  @override
  String get errorServiceUnavailable =>
      'This service is not available for booking right now.';

  @override
  String get errorNotFound => 'We couldn\'t find that.';

  @override
  String get errorCannotCancel =>
      'This appointment can no longer be cancelled.';

  @override
  String get reservationsTitle => 'My appointments';

  @override
  String get reservationsUpcoming => 'Upcoming';

  @override
  String get reservationsPast => 'Past and closed';

  @override
  String get reservationsEmptyTitle => 'No appointments yet';

  @override
  String get reservationsEmptyBody =>
      'When you book an appointment it will appear here.';

  @override
  String get reservationsFindCare => 'Find a provider';

  @override
  String get reservationDetailTitle => 'Appointment';

  @override
  String get reservationProvider => 'Provider';

  @override
  String get reservationService => 'Service';

  @override
  String get reservationWhen => 'Date and time';

  @override
  String get reservationDuration => 'Duration';

  @override
  String get reservationPrice => 'Price';

  @override
  String get reservationNote => 'Your note';

  @override
  String get reservationStatus => 'Status';

  @override
  String get reservationHistory => 'Status history';

  @override
  String get reservationViewProvider => 'View provider';

  @override
  String get statusPending => 'Pending';

  @override
  String get statusConfirmed => 'Confirmed';

  @override
  String get statusCompleted => 'Completed';

  @override
  String get statusRejected => 'Rejected';

  @override
  String get statusCancelled => 'Cancelled';

  @override
  String get statusNoShow => 'No show';

  @override
  String get statusUnknown => 'Unknown';

  @override
  String get cancelReservation => 'Cancel appointment';

  @override
  String get cancellingReservation => 'Cancelling…';

  @override
  String get cancelConfirmTitle => 'Cancel this appointment?';

  @override
  String get cancelConfirmBody => 'This cannot be undone.';

  @override
  String get cancelConfirmAction => 'Cancel appointment';

  @override
  String get cancelKeep => 'Keep appointment';

  @override
  String get cancelSuccess => 'The appointment was cancelled.';
}
