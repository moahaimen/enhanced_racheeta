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

  @override
  String get navWorkspace => 'Dashboard';

  @override
  String get navSchedule => 'Availability';

  @override
  String get navBookings => 'Bookings';

  @override
  String get providerOnly => 'This area is for provider accounts.';

  @override
  String get providerProfileMissing =>
      'Create your provider profile on the Racheeta website to use this area.';

  @override
  String get dashboardTitle => 'Dashboard';

  @override
  String get dashboardVerification => 'Verification';

  @override
  String get verificationUnverified => 'Not verified';

  @override
  String get verificationPending => 'Pending review';

  @override
  String get verificationVerified => 'Verified';

  @override
  String get verificationRejected => 'Rejected';

  @override
  String get verificationSuspended => 'Suspended';

  @override
  String get dashboardVisible => 'Visible to patients';

  @override
  String get dashboardHidden => 'Not visible to patients';

  @override
  String get dashboardReservations => 'Reservations';

  @override
  String get dashboardTotal => 'Total';

  @override
  String get dashboardUpcoming => 'Upcoming';

  @override
  String get dashboardUpcomingList => 'Upcoming appointments';

  @override
  String get dashboardNoUpcoming => 'No upcoming appointments.';

  @override
  String get dashboardReviews => 'Reviews';

  @override
  String get dashboardOffers => 'Offers';

  @override
  String get offersTotal => 'Total offers';

  @override
  String get offersRunning => 'Running now';

  @override
  String get offersScheduled => 'Scheduled';

  @override
  String get dashboardUnread => 'Unread';

  @override
  String get unreadNotifications => 'Notifications';

  @override
  String get unreadMessages => 'Messages';

  @override
  String get dashboardPractitioners => 'Practitioners';

  @override
  String get practitionersActive => 'Active';

  @override
  String get practitionersIncoming => 'Incoming requests';

  @override
  String get practitionersOutgoing => 'Outgoing invitations';

  @override
  String get scheduleTitle => 'Availability';

  @override
  String get scheduleAdd => 'Add availability';

  @override
  String get scheduleEmptyTitle => 'No upcoming availability';

  @override
  String get scheduleEmptyBody => 'Add the times patients can book.';

  @override
  String get scheduleNoneLoaded =>
      'No upcoming times in the pages loaded so far.';

  @override
  String get slotRemove => 'Remove';

  @override
  String get slotRemoving => 'Removing…';

  @override
  String get slotRemoveConfirmTitle => 'Remove this time?';

  @override
  String get slotRemoveConfirmBody =>
      'Patients will no longer be able to book it.';

  @override
  String get slotRemoveAction => 'Remove';

  @override
  String get slotKeep => 'Keep';

  @override
  String get slotRemoved => 'The time was removed.';

  @override
  String get slotCreated => 'Availability added.';

  @override
  String get slotFormTitle => 'Add availability';

  @override
  String get slotService => 'Service';

  @override
  String get slotPickDate => 'Choose a date';

  @override
  String get slotPickTime => 'Choose a start time';

  @override
  String get slotCreate => 'Create availability';

  @override
  String get slotCreating => 'Adding…';

  @override
  String get slotNoServices =>
      'You need an active service with a duration before adding availability. Set one up on the Racheeta website.';

  @override
  String get slotSelectAll => 'Choose a service, a date and a start time.';

  @override
  String get slotBack => 'Back to availability';

  @override
  String get errorSlotOverlap => 'This time overlaps another active time.';

  @override
  String get errorSlotPast => 'The start time must be in the future.';

  @override
  String get errorSlotService =>
      'This service can\'t be used for availability. It must be active and have a duration.';

  @override
  String get errorSlotInUse =>
      'A live booking uses this time, so it can\'t be removed.';

  @override
  String get bookingsTitle => 'Bookings';

  @override
  String get bookingsEmptyTitle => 'No bookings yet';

  @override
  String get bookingsEmptyBody => 'Bookings from patients will appear here.';

  @override
  String get bookingDetailTitle => 'Booking';

  @override
  String get patientLabel => 'Patient';

  @override
  String get patientNoteLabel => 'Patient\'s note';

  @override
  String get actionConfirm => 'Confirm';

  @override
  String get actionConfirming => 'Confirming…';

  @override
  String get actionReject => 'Reject';

  @override
  String get actionCancelBooking => 'Cancel booking';

  @override
  String get actionComplete => 'Mark as completed';

  @override
  String get actionNoShow => 'Mark as no-show';

  @override
  String get actionUpdating => 'Updating…';

  @override
  String get confirmRejectTitle => 'Reject this booking?';

  @override
  String get confirmRejectBody =>
      'The patient will see the new status. This cannot be undone.';

  @override
  String get confirmNoShowTitle => 'Mark as no-show?';

  @override
  String get confirmNoShowBody =>
      'The patient will see the new status. This cannot be undone.';

  @override
  String get confirmCancelBookingTitle => 'Cancel this booking?';

  @override
  String get confirmCancelBookingBody =>
      'The patient will see the new status. This cannot be undone.';

  @override
  String get confirmKeep => 'Keep booking';

  @override
  String get transitionDone => 'The booking was updated.';

  @override
  String get errorTransitionRefused =>
      'This booking can\'t be changed that way right now.';

  @override
  String get searchGenericHint => 'Search';

  @override
  String get filtersGenericTitle => 'Filters';

  @override
  String get realEstateTitle => 'Real estate';

  @override
  String get realEstateSearchHint => 'Search title, description or district';

  @override
  String get realEstateFiltersTitle => 'Filter properties';

  @override
  String get filterTransaction => 'Transaction';

  @override
  String get transactionSale => 'For sale';

  @override
  String get transactionRent => 'For rent';

  @override
  String get filterPropertyType => 'Property type';

  @override
  String get propertyClinic => 'Clinic';

  @override
  String get propertyApartmentForClinic => 'Apartment for a clinic';

  @override
  String get propertyMedicalBuilding => 'Medical building';

  @override
  String get propertyPharmacyLocation => 'Pharmacy location';

  @override
  String get propertyLaboratoryLocation => 'Laboratory location';

  @override
  String get propertyMedicalCenter => 'Medical center';

  @override
  String get propertyHospitalBuilding => 'Hospital building';

  @override
  String get propertyCommercialMedical => 'Commercial medical property';

  @override
  String get propertyInvestmentLand => 'Medical investment land';

  @override
  String get sortPriceAsc => 'Price: low to high';

  @override
  String get sortPriceDesc => 'Price: high to low';

  @override
  String get realEstateEmptyTitle => 'No properties found';

  @override
  String get priceOnRequest => 'Price on request';

  @override
  String get areaLabel => 'Area';

  @override
  String areaValue(String area) {
    return '$area m²';
  }

  @override
  String get districtLabel => 'District';

  @override
  String get suitableForLabel => 'Suitable for';

  @override
  String get facilitiesLabel => 'Facilities';

  @override
  String get listedByLabel => 'Listed by';

  @override
  String get sellerOwner => 'Owner';

  @override
  String get sellerAgent => 'Agent';

  @override
  String get useClinic => 'Clinic';

  @override
  String get usePharmacy => 'Pharmacy';

  @override
  String get useLaboratory => 'Laboratory';

  @override
  String get useMedicalCenter => 'Medical center';

  @override
  String get useHospital => 'Hospital';

  @override
  String get useGeneralMedical => 'General medical use';

  @override
  String get useMedicalInvestment => 'Medical investment';

  @override
  String get listingDetailTitle => 'Property';

  @override
  String get listingValidUntil => 'Listing valid until';

  @override
  String get sellerWorkspaceTitle => 'Property owner';

  @override
  String get sellerOnly => 'This area is for property-owner accounts.';

  @override
  String get sellerProfileMissing =>
      'Create your seller profile on the Racheeta website to use this area.';

  @override
  String get sellerListingsTotal => 'Total listings';

  @override
  String get sellerDraft => 'Drafts';

  @override
  String get sellerPublished => 'Published';

  @override
  String get sellerVisible => 'Visible to the public';

  @override
  String get sellerExpired => 'Expired';

  @override
  String get ownerListingsTitle => 'My listings';

  @override
  String get ownerListingsEmpty => 'You have no listings yet';

  @override
  String get ownerListingsEmptyBody =>
      'Create listings on the Racheeta website; you can publish them here.';

  @override
  String get ownerListingDetailTitle => 'My listing';

  @override
  String get statusDraft => 'Draft';

  @override
  String get statusPublished => 'Published';

  @override
  String get badgeVisible => 'Visible';

  @override
  String get badgeNotVisible => 'Not visible';

  @override
  String get badgeExpired => 'Expired';

  @override
  String get listingPublish => 'Publish';

  @override
  String get listingPublishing => 'Publishing…';

  @override
  String get listingUnpublish => 'Unpublish';

  @override
  String get listingUnpublishing => 'Unpublishing…';

  @override
  String get confirmUnpublishTitle => 'Unpublish this listing?';

  @override
  String get confirmUnpublishBody =>
      'It will no longer be visible to the public.';

  @override
  String get confirmKeepPublished => 'Keep published';

  @override
  String get listingPublished => 'The listing was published.';

  @override
  String get listingUnpublished => 'The listing was unpublished.';

  @override
  String get errorListingNotPublishable =>
      'This listing can\'t be published yet. Complete it on the Racheeta website.';

  @override
  String get errorSellerNotEligible =>
      'Your account can\'t manage listings right now.';

  @override
  String get exploreTitle => 'Explore';

  @override
  String get errorListingTransition =>
      'This listing can\'t be changed that way right now.';

  @override
  String get marketplaceTitle => 'Marketplace';

  @override
  String get marketplaceFiltersTitle => 'Filter products';

  @override
  String get marketplaceFilterCategory => 'Category';

  @override
  String get marketplaceEmptyTitle => 'No products available';

  @override
  String get marketplaceEmptyBody =>
      'Products appear when their category targets your profile.';

  @override
  String get errorMarketplaceBrowse =>
      'A verified provider profile is required to browse the marketplace.';

  @override
  String get productDetailTitle => 'Product';

  @override
  String get brandLabel => 'Brand';

  @override
  String get modelLabel => 'Model';

  @override
  String get categoryLabel => 'Category';

  @override
  String get supplierLabel => 'Supplier';

  @override
  String get companyWorkspaceTitle => 'Company workspace';

  @override
  String get companyOnly => 'This area is for medical company accounts.';

  @override
  String get companyProfileMissing =>
      'Create your company profile on the Racheeta website to use this area.';

  @override
  String get companyCanPublish => 'You can publish products.';

  @override
  String get companyCannotPublish =>
      'Publishing is unavailable until your company is verified.';

  @override
  String get productsTotal => 'Total products';

  @override
  String get productsActive => 'Active';

  @override
  String get productsInactive => 'Inactive';

  @override
  String get productsExposable => 'Visible to providers';

  @override
  String get companyProductsTitle => 'My products';

  @override
  String get companyProductsEmpty => 'You have no products yet';

  @override
  String get companyProductsEmptyBody =>
      'Create products on the Racheeta website; you can activate them here.';

  @override
  String get companyProductDetailTitle => 'My product';

  @override
  String get productStatusActive => 'Active';

  @override
  String get productStatusInactive => 'Inactive';

  @override
  String get productActivate => 'Activate';

  @override
  String get productActivating => 'Activating…';

  @override
  String get productDeactivate => 'Deactivate';

  @override
  String get productDeactivating => 'Deactivating…';

  @override
  String get confirmDeactivateTitle => 'Deactivate this product?';

  @override
  String get confirmDeactivateBody => 'Providers will no longer see it.';

  @override
  String get confirmKeepActive => 'Keep active';

  @override
  String get productActivated => 'The product was activated.';

  @override
  String get productDeactivated => 'The product was deactivated.';

  @override
  String get errorCompanyNotVerified =>
      'Your company must be verified before products can be activated.';

  @override
  String get errorCategoryUnavailable =>
      'This product\'s category can\'t be used for publishing right now.';

  @override
  String get errorProductTransition =>
      'This product can\'t be changed that way right now.';

  @override
  String get professionDoctor => 'Doctor';

  @override
  String get professionDentist => 'Dentist';

  @override
  String get professionPharmacist => 'Pharmacist';

  @override
  String get professionNurse => 'Nurse';

  @override
  String get professionMidwife => 'Midwife';

  @override
  String get professionLabTechnician => 'Laboratory technician';

  @override
  String get professionRadiologyTechnician => 'Radiology technician';

  @override
  String get professionAnesthesiaTechnician => 'Anesthesia technician';

  @override
  String get professionPhysiotherapist => 'Physiotherapist';

  @override
  String get professionNutritionist => 'Nutritionist';

  @override
  String get professionPsychologist => 'Psychologist';

  @override
  String get professionMedicalAssistant => 'Medical assistant';

  @override
  String get professionAdministrative => 'Administrative';

  @override
  String get professionOther => 'Other';

  @override
  String get employmentFullTime => 'Full time';

  @override
  String get employmentPartTime => 'Part time';

  @override
  String get employmentContract => 'Contract';

  @override
  String get employmentTemporary => 'Temporary';

  @override
  String get employmentInternship => 'Internship';

  @override
  String get employmentLocum => 'Locum';

  @override
  String get workModeOnSite => 'On site';

  @override
  String get workModeRemote => 'Remote';

  @override
  String get workModeHybrid => 'Hybrid';

  @override
  String get shiftDay => 'Day';

  @override
  String get shiftNight => 'Night';

  @override
  String get shiftRotating => 'Rotating';

  @override
  String get shiftFlexible => 'Flexible';

  @override
  String get shiftOnCall => 'On call';

  @override
  String get degreeDiploma => 'Diploma';

  @override
  String get degreeBachelor => 'Bachelor';

  @override
  String get degreeHigherDiploma => 'Higher diploma';

  @override
  String get degreeMaster => 'Master';

  @override
  String get degreePhd => 'PhD';

  @override
  String get degreeBoard => 'Board certification';

  @override
  String get degreeOther => 'Other';

  @override
  String get jobStatusDraft => 'Draft';

  @override
  String get jobStatusPendingAdminReview => 'Pending review';

  @override
  String get jobStatusPublished => 'Published';

  @override
  String get jobStatusClosed => 'Closed';

  @override
  String get jobStatusExpired => 'Expired';

  @override
  String get jobStatusRejected => 'Rejected';

  @override
  String get jobStatusSuspended => 'Suspended';

  @override
  String get jobStatusArchived => 'Archived';

  @override
  String get applicationStatusSubmitted => 'Submitted';

  @override
  String get applicationStatusReviewing => 'Under review';

  @override
  String get applicationStatusShortlisted => 'Shortlisted';

  @override
  String get applicationStatusInterview => 'Interview';

  @override
  String get applicationStatusAccepted => 'Accepted';

  @override
  String get applicationStatusRejected => 'Rejected';

  @override
  String get applicationStatusWithdrawn => 'Withdrawn';

  @override
  String get jobsTitle => 'Jobs';

  @override
  String get jobsSearchHint => 'Search jobs';

  @override
  String get jobsFiltersTitle => 'Filter jobs';

  @override
  String get filterProfession => 'Profession';

  @override
  String get filterEmploymentType => 'Employment type';

  @override
  String get filterWorkMode => 'Work mode';

  @override
  String get jobsEmptyTitle => 'No jobs found';

  @override
  String get jobDetailTitle => 'Job';

  @override
  String get jobEmployerLabel => 'Employer';

  @override
  String jobOnBehalfOf(String name) {
    return 'On behalf of $name';
  }

  @override
  String get jobSalaryLabel => 'Salary';

  @override
  String jobSalaryRange(String min, String max, String currency) {
    return '$min – $max $currency';
  }

  @override
  String jobSalaryFrom(String min, String currency) {
    return 'From $min $currency';
  }

  @override
  String jobSalaryUpTo(String max, String currency) {
    return 'Up to $max $currency';
  }

  @override
  String get jobDeadlineLabel => 'Apply by';

  @override
  String get jobOpeningsLabel => 'Openings';

  @override
  String get jobExperienceLabel => 'Minimum experience';

  @override
  String jobExperienceYears(int years) {
    return '$years years';
  }

  @override
  String get jobDegreeLabel => 'Minimum degree';

  @override
  String get jobShiftLabel => 'Shift';

  @override
  String get jobSpecialtyLabel => 'Specialty';

  @override
  String get jobResponsibilitiesLabel => 'Responsibilities';

  @override
  String get jobRequirementsLabel => 'Requirements';

  @override
  String get jobWorkplaceLabel => 'Workplace';

  @override
  String get jobFeaturedBadge => 'Featured';

  @override
  String get jobClosedNotice => 'This job is not open for applications.';

  @override
  String get applyTitle => 'Apply for this job';

  @override
  String get applyCoverText => 'Cover note (optional)';

  @override
  String applyCoverTooLong(int max) {
    return 'The note must be at most $max characters.';
  }

  @override
  String get applyAction => 'Send application';

  @override
  String get applyPending => 'Sending…';

  @override
  String get applySent => 'Your application was sent.';

  @override
  String get applyViewMine => 'View my applications';

  @override
  String get errorProfileRequired =>
      'Create your professional profile on the Racheeta website to apply.';

  @override
  String get errorJobNotOpen => 'This job is no longer open for applications.';

  @override
  String get errorDeadlinePassed => 'The application deadline has passed.';

  @override
  String get errorAlreadyApplied => 'You have already applied to this job.';

  @override
  String get errorContactNotAllowed =>
      'Remove phone numbers, e-mail addresses and links from the note.';

  @override
  String get errorApplicationLimit =>
      'Your plan doesn\'t allow more applications right now.';

  @override
  String get myApplicationsTitle => 'My applications';

  @override
  String get myApplicationsEmpty => 'You haven\'t applied to any job yet';

  @override
  String get myApplicationsEmptyBody => 'Applications you send appear here.';

  @override
  String applicationSubmittedOn(String date) {
    return 'Sent $date';
  }

  @override
  String get applicationWithdraw => 'Withdraw';

  @override
  String get applicationWithdrawing => 'Withdrawing…';

  @override
  String get confirmWithdrawTitle => 'Withdraw this application?';

  @override
  String get confirmWithdrawBody =>
      'The employer will see it as withdrawn. This cannot be undone.';

  @override
  String get confirmKeepApplication => 'Keep application';

  @override
  String get applicationWithdrawn => 'The application was withdrawn.';

  @override
  String get errorApplicationTransition =>
      'This application can\'t be changed that way right now.';

  @override
  String get recruiterWorkspaceTitle => 'Recruiter workspace';

  @override
  String get recruiterOnly =>
      'This area is for recruiting-organisation members.';

  @override
  String get recruiterProfileMissing =>
      'You are not a member of a recruiting organisation.';

  @override
  String get recruiterOrganization => 'Organisation';

  @override
  String get recruiterMyRole => 'My role';

  @override
  String get recruiterRecruitmentStatus => 'Recruitment';

  @override
  String get recruiterCanRecruit => 'This organisation can recruit.';

  @override
  String get recruiterCannotRecruit =>
      'This organisation can\'t recruit right now.';

  @override
  String get recruiterJobsHeading => 'Jobs';

  @override
  String get recruiterOpenNow => 'Open now';

  @override
  String get recruiterApplicationsHeading => 'Applications';

  @override
  String get recruiterAwaitingReview => 'Awaiting review';

  @override
  String get recruiterLast7Days => 'Last 7 days';

  @override
  String get recruiterApplicationsWithheld =>
      'Application figures are not available for this account.';

  @override
  String get recruiterInterviewsHeading => 'Interviews';

  @override
  String get recruiterSeatsHeading => 'Seats';

  @override
  String get recruiterSeatsActive => 'Active members';

  @override
  String get recruiterSeatsLimit => 'Limit';

  @override
  String get recruiterOpenJobs => 'Organisation jobs';

  @override
  String get recruiterJobsTitle => 'Organisation jobs';

  @override
  String get recruiterJobsEmpty => 'No jobs yet';

  @override
  String get recruiterJobsEmptyBody =>
      'Create jobs on the Racheeta website; you can follow and close them here.';

  @override
  String get recruiterJobDetailTitle => 'Organisation job';

  @override
  String get recruiterApplicationsCount => 'Applications received';

  @override
  String get filterJobStatus => 'Status';

  @override
  String get jobClose => 'Close job';

  @override
  String get jobClosing => 'Closing…';

  @override
  String get confirmCloseJobTitle => 'Close this job?';

  @override
  String get confirmCloseJobBody => 'It will stop accepting applications.';

  @override
  String get confirmKeepJob => 'Keep open';

  @override
  String get jobClosedDone => 'The job was closed.';

  @override
  String get errorMembershipInactive =>
      'Your membership no longer allows this action.';

  @override
  String get errorJobTransition =>
      'This job can\'t be changed that way right now.';

  @override
  String get notificationsTitle => 'Notifications';

  @override
  String get notificationsEmpty => 'No notifications yet';

  @override
  String get notificationsEmptyBody =>
      'Updates about your reservations appear here.';

  @override
  String get notificationsMarkAll => 'Mark all as read';

  @override
  String get notificationsMarkingAll => 'Marking…';

  @override
  String notificationsAllMarked(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count notifications marked as read.',
      one: '1 notification marked as read.',
      zero: 'Nothing to mark.',
    );
    return '$_temp0';
  }

  @override
  String notificationsUnreadCount(int count) {
    return '$count unread';
  }

  @override
  String get notificationUnread => 'Unread';

  @override
  String get notificationRead => 'Read';

  @override
  String get notificationFallbackTitle => 'Notification';

  @override
  String get errorNotificationMark =>
      'Couldn\'t update the notification. Try again.';

  @override
  String get pushPromptTitle => 'Get push notifications';

  @override
  String get pushPromptBody =>
      'Allow notifications to be alerted about new activity. Everything also stays here without them.';

  @override
  String get pushPromptAction => 'Allow notifications';

  @override
  String get pushDeniedHint =>
      'Push notifications are off for this app. You can turn them on in system settings; everything still appears here.';

  @override
  String get chatTitle => 'Messages';

  @override
  String get conversationTitle => 'Conversation';

  @override
  String get chatEmpty => 'No conversations yet';

  @override
  String get chatEmptyBody =>
      'Conversations about your reservations appear here once one is opened.';

  @override
  String get chatContextReservation => 'Reservation conversation';

  @override
  String get chatContextOther => 'Conversation';

  @override
  String get chatNoMessages => 'No messages yet. Say hello.';

  @override
  String get chatLoadOlder => 'Load earlier messages';

  @override
  String get chatLoadOlderFailed => 'Couldn\'t load earlier messages.';

  @override
  String get chatComposerLabel => 'Message';

  @override
  String get chatSend => 'Send';

  @override
  String get chatSending => 'Sending…';

  @override
  String get chatErrorBlank => 'Write a message first.';

  @override
  String chatErrorTooLong(int max) {
    return 'A message can be at most $max characters.';
  }

  @override
  String get chatErrorSend => 'Your message wasn\'t sent. Try again.';

  @override
  String get chatYou => 'You';

  @override
  String chatUnread(int count) {
    return '$count unread';
  }

  @override
  String get chatMessageProvider => 'Message the provider';

  @override
  String get chatMessagePatient => 'Message the patient';

  @override
  String get chatOpening => 'Opening…';

  @override
  String get chatOpenFailed => 'Couldn\'t open the conversation.';
}
