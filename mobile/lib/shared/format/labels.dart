import '../../features/reservations/data/reservation_models.dart';
import '../../l10n/generated/app_localizations.dart';

/// Localised names for backend enum codes. Unknown future codes fall back to the raw code rather
/// than hiding the record.
String providerTypeLabel(AppLocalizations l10n, String code) => switch (code) {
  'DOCTOR' => l10n.providerTypeDoctor,
  'NURSE' => l10n.providerTypeNurse,
  'THERAPIST' => l10n.providerTypeTherapist,
  'HOSPITAL' => l10n.providerTypeHospital,
  'MEDICAL_CENTER' => l10n.providerTypeMedicalCenter,
  'PHARMACY' => l10n.providerTypePharmacy,
  'LABORATORY' => l10n.providerTypeLaboratory,
  'BEAUTY_CENTER' => l10n.providerTypeBeautyCenter,
  _ => code,
};

String providerKindLabel(AppLocalizations l10n, String code) => switch (code) {
  'PRACTITIONER' => l10n.kindPractitioner,
  'FACILITY' => l10n.kindFacility,
  _ => code,
};

String reservationStatusLabel(
  AppLocalizations l10n,
  ReservationStatus status,
) => switch (status) {
  ReservationStatus.pending => l10n.statusPending,
  ReservationStatus.confirmed => l10n.statusConfirmed,
  ReservationStatus.completed => l10n.statusCompleted,
  ReservationStatus.rejected => l10n.statusRejected,
  ReservationStatus.cancelled => l10n.statusCancelled,
  ReservationStatus.noShow => l10n.statusNoShow,
  ReservationStatus.unknown => l10n.statusUnknown,
};
