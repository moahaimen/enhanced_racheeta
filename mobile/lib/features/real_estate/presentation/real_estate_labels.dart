import '../../../l10n/generated/app_localizations.dart';
import '../../discovery/data/discovery_models.dart' show Place;

/// Localised names for the backend's controlled vocabularies. An unknown future code falls back to
/// the raw code rather than hiding the record.
String propertyTypeLabel(AppLocalizations l10n, String code) => switch (code) {
  'CLINIC' => l10n.propertyClinic,
  'APARTMENT_FOR_CLINIC' => l10n.propertyApartmentForClinic,
  'MEDICAL_BUILDING' => l10n.propertyMedicalBuilding,
  'PHARMACY_LOCATION' => l10n.propertyPharmacyLocation,
  'LABORATORY_LOCATION' => l10n.propertyLaboratoryLocation,
  'MEDICAL_CENTER' => l10n.propertyMedicalCenter,
  'HOSPITAL_BUILDING' => l10n.propertyHospitalBuilding,
  'COMMERCIAL_MEDICAL_PROPERTY' => l10n.propertyCommercialMedical,
  'MEDICAL_INVESTMENT_LAND' => l10n.propertyInvestmentLand,
  _ => code,
};

String transactionLabel(AppLocalizations l10n, String code) => switch (code) {
  'SALE' => l10n.transactionSale,
  'RENT' => l10n.transactionRent,
  _ => code,
};

String suitableUseLabel(AppLocalizations l10n, String code) => switch (code) {
  'CLINIC' => l10n.useClinic,
  'PHARMACY' => l10n.usePharmacy,
  'LABORATORY' => l10n.useLaboratory,
  'MEDICAL_CENTER' => l10n.useMedicalCenter,
  'HOSPITAL' => l10n.useHospital,
  'GENERAL_MEDICAL_USE' => l10n.useGeneralMedical,
  'MEDICAL_INVESTMENT' => l10n.useMedicalInvestment,
  _ => code,
};

String sellerTypeLabel(AppLocalizations l10n, String code) => switch (code) {
  'OWNER' => l10n.sellerOwner,
  'AGENT' => l10n.sellerAgent,
  _ => code,
};

String publicationLabel(AppLocalizations l10n, String code) => switch (code) {
  'DRAFT' => l10n.statusDraft,
  'PUBLISHED' => l10n.statusPublished,
  _ => code,
};

/// "City، Governorate" from the names the backend supplied.
String placeLine(Place? city, Place? governorate, String languageCode) => [
  city?.name(languageCode),
  governorate?.name(languageCode),
].whereType<String>().where((name) => name.isNotEmpty).join('، ');

/// The ordering and filter codes the catalogue sends (documented backend values). They are
/// contract-tested against `docs/api/openapi.yaml`.
const propertyTypeCodes = <String>[
  'CLINIC',
  'APARTMENT_FOR_CLINIC',
  'MEDICAL_BUILDING',
  'PHARMACY_LOCATION',
  'LABORATORY_LOCATION',
  'MEDICAL_CENTER',
  'HOSPITAL_BUILDING',
  'COMMERCIAL_MEDICAL_PROPERTY',
  'MEDICAL_INVESTMENT_LAND',
];
const transactionCodes = <String>['SALE', 'RENT'];
const listingOrderingCodes = <String>['price', '-price'];
