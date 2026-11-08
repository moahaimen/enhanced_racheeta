import '../../../l10n/generated/app_localizations.dart';

/// Localised names for the backend's controlled vocabularies. An unknown future code falls back to
/// the raw code rather than hiding the record. The code lists below are contract-tested against
/// `docs/api/openapi.yaml`.
String professionLabel(AppLocalizations l10n, String code) => switch (code) {
  'DOCTOR' => l10n.professionDoctor,
  'DENTIST' => l10n.professionDentist,
  'PHARMACIST' => l10n.professionPharmacist,
  'NURSE' => l10n.professionNurse,
  'MIDWIFE' => l10n.professionMidwife,
  'LAB_TECHNICIAN' => l10n.professionLabTechnician,
  'RADIOLOGY_TECHNICIAN' => l10n.professionRadiologyTechnician,
  'ANESTHESIA_TECHNICIAN' => l10n.professionAnesthesiaTechnician,
  'PHYSIOTHERAPIST' => l10n.professionPhysiotherapist,
  'NUTRITIONIST' => l10n.professionNutritionist,
  'PSYCHOLOGIST' => l10n.professionPsychologist,
  'MEDICAL_ASSISTANT' => l10n.professionMedicalAssistant,
  'PHARMACY_TECHNICIAN' => l10n.professionPharmacyTechnician,
  'OPTOMETRIST' => l10n.professionOptometrist,
  'SPEECH_THERAPIST' => l10n.professionSpeechTherapist,
  'OTHER' => l10n.professionOther,
  'BIOMEDICAL_ENGINEER' => l10n.professionBiomedicalEngineer,
  'MEDICAL_REPRESENTATIVE' => l10n.professionMedicalRepresentative,
  'HEALTH_ADMINISTRATOR' => l10n.professionHealthAdministrator,
  'ADMINISTRATIVE' => l10n.professionAdministrative,
  'SOFTWARE_DEVELOPER' => l10n.professionSoftwareDeveloper,
  'IT_SUPPORT' => l10n.professionItSupport,
  'NETWORK_ENGINEER' => l10n.professionNetworkEngineer,
  'CYBERSECURITY' => l10n.professionCybersecurity,
  'DATA_ANALYST' => l10n.professionDataAnalyst,
  'ACCOUNTANT' => l10n.professionAccountant,
  'MARKETING' => l10n.professionMarketing,
  'SALES' => l10n.professionSales,
  'HUMAN_RESOURCES' => l10n.professionHumanResources,
  'ENGINEER' => l10n.professionEngineer,
  'CUSTOMER_SERVICE' => l10n.professionCustomerService,
  'MANAGER' => l10n.professionManager,
  'OPERATIONS' => l10n.professionOperations,
  'TEACHER' => l10n.professionTeacher,
  'OTHER_PROFESSION' => l10n.professionOtherProfession,
  _ => code,
};

String employmentTypeLabel(AppLocalizations l10n, String code) =>
    switch (code) {
      'FULL_TIME' => l10n.employmentFullTime,
      'PART_TIME' => l10n.employmentPartTime,
      'CONTRACT' => l10n.employmentContract,
      'TEMPORARY' => l10n.employmentTemporary,
      'INTERNSHIP' => l10n.employmentInternship,
      'LOCUM' => l10n.employmentLocum,
      _ => code,
    };

String workModeLabel(AppLocalizations l10n, String code) => switch (code) {
  'ON_SITE' => l10n.workModeOnSite,
  'REMOTE' => l10n.workModeRemote,
  'HYBRID' => l10n.workModeHybrid,
  _ => code,
};

String shiftTypeLabel(AppLocalizations l10n, String code) => switch (code) {
  'DAY' => l10n.shiftDay,
  'NIGHT' => l10n.shiftNight,
  'ROTATING' => l10n.shiftRotating,
  'FLEXIBLE' => l10n.shiftFlexible,
  'ON_CALL' => l10n.shiftOnCall,
  _ => code,
};

String degreeLabel(AppLocalizations l10n, String code) => switch (code) {
  'DIPLOMA' => l10n.degreeDiploma,
  'BACHELOR' => l10n.degreeBachelor,
  'HIGHER_DIPLOMA' => l10n.degreeHigherDiploma,
  'MASTER' => l10n.degreeMaster,
  'PHD' => l10n.degreePhd,
  'BOARD' => l10n.degreeBoard,
  'OTHER' => l10n.degreeOther,
  _ => code,
};

String jobStatusLabel(AppLocalizations l10n, String code) => switch (code) {
  'DRAFT' => l10n.jobStatusDraft,
  'PENDING_ADMIN_REVIEW' => l10n.jobStatusPendingAdminReview,
  'PUBLISHED' => l10n.jobStatusPublished,
  'CLOSED' => l10n.jobStatusClosed,
  'EXPIRED' => l10n.jobStatusExpired,
  'REJECTED' => l10n.jobStatusRejected,
  'SUSPENDED' => l10n.jobStatusSuspended,
  'ARCHIVED' => l10n.jobStatusArchived,
  _ => code,
};

String applicationStatusLabel(AppLocalizations l10n, String code) =>
    switch (code) {
      'SUBMITTED' => l10n.applicationStatusSubmitted,
      'REVIEWING' => l10n.applicationStatusReviewing,
      'SHORTLISTED' => l10n.applicationStatusShortlisted,
      'INTERVIEW' => l10n.applicationStatusInterview,
      'ACCEPTED' => l10n.applicationStatusAccepted,
      'REJECTED' => l10n.applicationStatusRejected,
      'WITHDRAWN' => l10n.applicationStatusWithdrawn,
      _ => code,
    };

// Healthcare first, then the other fields (same order as the backend's PROFESSION_GROUPS).
const professionCodes = <String>[
  'DOCTOR',
  'DENTIST',
  'PHARMACIST',
  'NURSE',
  'MIDWIFE',
  'LAB_TECHNICIAN',
  'RADIOLOGY_TECHNICIAN',
  'ANESTHESIA_TECHNICIAN',
  'PHYSIOTHERAPIST',
  'NUTRITIONIST',
  'PSYCHOLOGIST',
  'MEDICAL_ASSISTANT',
  'PHARMACY_TECHNICIAN',
  'OPTOMETRIST',
  'SPEECH_THERAPIST',
  'OTHER',
  'BIOMEDICAL_ENGINEER',
  'MEDICAL_REPRESENTATIVE',
  'HEALTH_ADMINISTRATOR',
  'ADMINISTRATIVE',
  'SOFTWARE_DEVELOPER',
  'IT_SUPPORT',
  'NETWORK_ENGINEER',
  'CYBERSECURITY',
  'DATA_ANALYST',
  'ACCOUNTANT',
  'MARKETING',
  'SALES',
  'HUMAN_RESOURCES',
  'ENGINEER',
  'CUSTOMER_SERVICE',
  'MANAGER',
  'OPERATIONS',
  'TEACHER',
  'OTHER_PROFESSION',
];
const employmentTypeCodes = <String>[
  'FULL_TIME',
  'PART_TIME',
  'CONTRACT',
  'TEMPORARY',
  'INTERNSHIP',
  'LOCUM',
];
const workModeCodes = <String>['ON_SITE', 'REMOTE', 'HYBRID'];
const shiftTypeCodes = <String>[
  'DAY',
  'NIGHT',
  'ROTATING',
  'FLEXIBLE',
  'ON_CALL',
];
const degreeCodes = <String>[
  'DIPLOMA',
  'BACHELOR',
  'HIGHER_DIPLOMA',
  'MASTER',
  'PHD',
  'BOARD',
  'OTHER',
];
const jobStatusCodes = <String>[
  'DRAFT',
  'PENDING_ADMIN_REVIEW',
  'PUBLISHED',
  'CLOSED',
  'EXPIRED',
  'REJECTED',
  'SUSPENDED',
  'ARCHIVED',
];
const applicationStatusCodes = <String>[
  'SUBMITTED',
  'REVIEWING',
  'SHORTLISTED',
  'INTERVIEW',
  'ACCEPTED',
  'REJECTED',
  'WITHDRAWN',
];
