import 'package:flutter/foundation.dart';

import '../../../core/api/json_reader.dart';
import '../../discovery/data/discovery_models.dart' show Place;

/// `SellerSummary` (the public listing's seller: profile id and display name only).
@immutable
class SellerSummary {
  const SellerSummary({
    required this.id,
    required this.displayName,
    required this.sellerType,
  });

  factory SellerSummary.fromJson(Object? json) {
    final r = JsonReader.of(json, 'SellerSummary');
    return SellerSummary(
      id: r.string('id'),
      displayName: r.string('display_name'),
      sellerType: r.stringOr('seller_type'),
    );
  }

  final String id;
  final String displayName;

  /// `SellerTypeEnum` code (`OWNER`, `AGENT`); unknown codes are kept.
  final String sellerType;
}

/// A property listing: `PropertyListingPublic` (public catalogue) or `PropertyListingOwner` (the
/// seller's own view, which adds the lifecycle fields). Codes (`property_type`, `transaction_type`,
/// uses, status) are kept as the backend sent them so an unknown future value still renders. The
/// price is the backend's decimal string; `null` means "price on request". No coordinates are used:
/// there is no map in this phase.
@immutable
class PropertyListing {
  const PropertyListing({
    required this.id,
    required this.title,
    required this.description,
    required this.propertyType,
    required this.transactionType,
    required this.governorate,
    required this.city,
    required this.district,
    required this.areaSqm,
    required this.price,
    required this.currency,
    required this.suitableUses,
    required this.facilities,
    required this.contactMethod,
    required this.contactPhone,
    required this.contactEmail,
    required this.publishedAt,
    required this.expiresAt,
    this.seller,
    this.publicationStatus,
    this.isPublic,
    this.isExpired,
  });

  factory PropertyListing.fromPublicJson(Object? json) {
    final r = JsonReader.of(json, 'PropertyListingPublic');
    return PropertyListing._parse(
      r,
      seller: SellerSummary.fromJson(r.raw('seller')),
    );
  }

  factory PropertyListing.fromOwnerJson(Object? json) {
    final r = JsonReader.of(json, 'PropertyListingOwner');
    return PropertyListing._parse(
      r,
      publicationStatus: r.string('publication_status'),
      isPublic: r.boolean('is_public'),
      isExpired: r.boolean('is_expired'),
    );
  }

  factory PropertyListing._parse(
    JsonReader r, {
    SellerSummary? seller,
    String? publicationStatus,
    bool? isPublic,
    bool? isExpired,
  }) => PropertyListing(
    id: r.string('id'),
    title: r.string('title'),
    description: r.stringOr('description'),
    propertyType: r.string('property_type'),
    transactionType: r.string('transaction_type'),
    governorate: r.optional('governorate', Place.fromJson),
    city: r.optional('city', Place.fromJson),
    district: r.stringOr('district'),
    areaSqm: r.stringOrNull('area_sqm'),
    price: r.stringOrNull('price'),
    currency: r.stringOr('currency'),
    suitableUses: r.listOrEmpty<String>('suitable_uses', (v) => v! as String),
    facilities: r.stringOr('facilities'),
    contactMethod: r.stringOr('contact_method'),
    contactPhone: r.stringOrNull('contact_phone'),
    contactEmail: r.stringOrNull('contact_email'),
    publishedAt: r.instantOrNull('published_at'),
    expiresAt: r.instantOrNull('expires_at'),
    seller: seller,
    publicationStatus: publicationStatus,
    isPublic: isPublic,
    isExpired: isExpired,
  );

  final String id;
  final String title;
  final String description;
  final String propertyType;
  final String transactionType;
  final Place? governorate;
  final Place? city;
  final String district;
  final String? areaSqm;
  final String? price;
  final String currency;
  final List<String> suitableUses;
  final String facilities;
  final String contactMethod;
  final String? contactPhone;
  final String? contactEmail;
  final DateTime? publishedAt;
  final DateTime? expiresAt;

  /// Public listings only.
  final SellerSummary? seller;

  /// Owner listings only: `PublicationStatusEnum` (`DRAFT`, `PUBLISHED`), and the backend's own
  /// verdicts on whether the listing is publicly visible / expired right now.
  final String? publicationStatus;
  final bool? isPublic;
  final bool? isExpired;

  /// No personal or contact data in the string form (logs).
  @override
  String toString() => 'PropertyListing($propertyType, $transactionType)';
}

/// `OwnerDashboard`: counts computed by the backend; no views, leads or revenue exist.
@immutable
class OwnerDashboard {
  const OwnerDashboard({
    required this.total,
    required this.draft,
    required this.published,
    required this.visible,
    required this.expired,
    required this.sale,
    required this.rent,
  });

  factory OwnerDashboard.fromJson(Object? json) {
    final r = JsonReader.of(json, 'OwnerDashboard');
    return OwnerDashboard(
      total: r.integer('listings_total'),
      draft: r.integer('listings_draft'),
      published: r.integer('listings_published'),
      visible: r.integer('listings_visible'),
      expired: r.integer('listings_expired'),
      sale: r.integer('listings_sale'),
      rent: r.integer('listings_rent'),
    );
  }

  final int total;
  final int draft;
  final int published;
  final int visible;
  final int expired;
  final int sale;
  final int rent;
}
