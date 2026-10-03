import 'package:flutter/foundation.dart';

import '../../../core/api/json_reader.dart';

/// `Specialty` (docs/api/openapi.yaml). Names are bilingual, chosen by the UI language.
@immutable
class Specialty {
  const Specialty({
    required this.id,
    required this.slug,
    required this.nameAr,
    required this.nameEn,
  });

  factory Specialty.fromJson(Object? json) {
    final r = JsonReader.of(json, 'Specialty');
    return Specialty(
      id: r.string('id'),
      slug: r.string('slug'),
      nameAr: r.string('name_ar'),
      nameEn: r.string('name_en'),
    );
  }

  final String id;
  final String slug;
  final String nameAr;
  final String nameEn;

  String name(String languageCode) => languageCode == 'ar'
      ? (nameAr.isEmpty ? nameEn : nameAr)
      : (nameEn.isEmpty ? nameAr : nameEn);
}

/// `Governorate` / `City` reference data (`/geo/*`).
@immutable
class Place {
  const Place({
    required this.id,
    required this.slug,
    required this.nameAr,
    required this.nameEn,
  });

  factory Place.fromJson(Object? json) {
    final r = JsonReader.of(json, 'Place');
    return Place(
      id: r.string('id'),
      slug: r.string('slug'),
      nameAr: r.string('name_ar'),
      nameEn: r.string('name_en'),
    );
  }

  final String id;
  final String slug;
  final String nameAr;
  final String nameEn;

  String name(String languageCode) => languageCode == 'ar'
      ? (nameAr.isEmpty ? nameEn : nameAr)
      : (nameEn.isEmpty ? nameAr : nameEn);
}

/// `ProviderCard`: a discovery list item.
@immutable
class ProviderCard {
  const ProviderCard({
    required this.id,
    required this.displayName,
    required this.kind,
    required this.providerType,
    required this.specialties,
    required this.governorate,
    required this.city,
    required this.averageRating,
    required this.reviewCount,
  });

  factory ProviderCard.fromJson(Object? json) {
    final r = JsonReader.of(json, 'ProviderCard');
    return ProviderCard(
      id: r.string('id'),
      displayName: r.string('display_name'),
      kind: r.stringOr('kind'),
      providerType: r.stringOr('provider_type'),
      specialties: r.listOrEmpty('specialties', Specialty.fromJson),
      governorate: r.optional('governorate', Place.fromJson),
      city: r.optional('city', Place.fromJson),
      averageRating: r.doubleOrNull('average_rating'),
      reviewCount: r.integerOrNull('review_count') ?? 0,
    );
  }

  final String id;
  final String displayName;

  /// `PRACTITIONER` or `FACILITY` (backend-derived).
  final String kind;

  /// `ProviderTypeEnum` code, e.g. `DOCTOR`. Unknown future codes are kept as-is.
  final String providerType;
  final List<Specialty> specialties;
  final Place? governorate;
  final Place? city;

  /// Null when there are no reviews (never invented).
  final double? averageRating;
  final int reviewCount;
}

/// `PublicService`: a bookable service of a provider.
@immutable
class PublicService {
  const PublicService({
    required this.id,
    required this.title,
    required this.description,
    required this.durationMinutes,
    required this.price,
    required this.currency,
    required this.specialty,
  });

  factory PublicService.fromJson(Object? json) {
    final r = JsonReader.of(json, 'PublicService');
    return PublicService(
      id: r.string('id'),
      title: r.string('title'),
      description: r.stringOr('description'),
      durationMinutes: r.integerOrNull('duration_minutes'),
      price: r.stringOr('price'),
      currency: r.stringOr('currency'),
      specialty: r.optional('specialty', Specialty.fromJson),
    );
  }

  final String id;
  final String title;
  final String description;

  /// Null when the provider has not set one (such a service cannot have slots).
  final int? durationMinutes;

  /// Decimal as sent by the server; formatted for display, never used for arithmetic.
  final String price;
  final String currency;
  final Specialty? specialty;
}

/// `RelatedProvider`: an active, itself-discoverable membership counterpart.
@immutable
class RelatedProvider {
  const RelatedProvider({
    required this.id,
    required this.displayName,
    required this.providerType,
    required this.kind,
  });

  factory RelatedProvider.fromJson(Object? json) {
    final r = JsonReader.of(json, 'RelatedProvider');
    return RelatedProvider(
      id: r.string('id'),
      displayName: r.string('display_name'),
      providerType: r.stringOr('provider_type'),
      kind: r.stringOr('kind'),
    );
  }

  final String id;
  final String displayName;
  final String providerType;
  final String kind;
}

/// `ProviderPublic`: the full public profile. Only fields the public API returns; nothing else is
/// derived or invented (no badges beyond `verified_at`, no coordinates are rendered).
@immutable
class ProviderPublic {
  const ProviderPublic({
    required this.card,
    required this.about,
    required this.address,
    required this.phone,
    required this.publicEmail,
    required this.website,
    required this.verifiedAt,
    required this.services,
    required this.relatedProviders,
  });

  factory ProviderPublic.fromJson(Object? json) {
    final r = JsonReader.of(json, 'ProviderPublic');
    return ProviderPublic(
      card: ProviderCard.fromJson(json),
      about: r.stringOr('about'),
      address: r.stringOr('address'),
      phone: r.stringOr('phone'),
      publicEmail: r.stringOr('public_email'),
      website: r.stringOr('website'),
      verifiedAt: r.instantOrNull('verified_at'),
      services: r.listOrEmpty('services', PublicService.fromJson),
      relatedProviders: r.listOrEmpty(
        'related_providers',
        RelatedProvider.fromJson,
      ),
    );
  }

  final ProviderCard card;
  final String about;
  final String address;
  final String phone;
  final String publicEmail;
  final String website;

  /// Non-null only when the backend reports a verification time.
  final DateTime? verifiedAt;
  final List<PublicService> services;
  final List<RelatedProvider> relatedProviders;
}

/// `AvailabilitySlot` from the public availability endpoint. Times are UTC instants.
@immutable
class AvailabilitySlot {
  const AvailabilitySlot({
    required this.id,
    required this.startsAt,
    required this.endsAt,
    required this.service,
    required this.providerId,
  });

  factory AvailabilitySlot.fromJson(Object? json) {
    final r = JsonReader.of(json, 'AvailabilitySlot');
    return AvailabilitySlot(
      id: r.string('id'),
      startsAt: r.instant('starts_at'),
      endsAt: r.instant('ends_at'),
      service: PublicService.fromJson(r.raw('service')),
      providerId: r.object('provider').string('id'),
    );
  }

  final String id;
  final DateTime startsAt;
  final DateTime endsAt;
  final PublicService service;
  final String providerId;
}
