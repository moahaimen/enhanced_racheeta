import 'package:flutter/foundation.dart';

import '../../../core/api/json_reader.dart';
import '../../discovery/data/discovery_models.dart' show Place;

/// `ProductCategory` (reference data, bilingual).
@immutable
class ProductCategory {
  const ProductCategory({
    required this.id,
    required this.slug,
    required this.nameAr,
    required this.nameEn,
    required this.canPublish,
  });

  factory ProductCategory.fromJson(Object? json) {
    final r = JsonReader.of(json, 'ProductCategory');
    return ProductCategory(
      id: r.string('id'),
      slug: r.string('slug'),
      nameAr: r.string('name_ar'),
      nameEn: r.string('name_en'),
      canPublish: r.booleanOr('can_publish', fallback: false),
    );
  }

  final String id;
  final String slug;
  final String nameAr;
  final String nameEn;

  /// Backend-derived guidance (an active category with at least one active audience rule).
  final bool canPublish;

  String name(String languageCode) {
    final preferred = languageCode == 'ar' ? nameAr : nameEn;
    return preferred.isNotEmpty
        ? preferred
        : (nameEn.isNotEmpty ? nameEn : nameAr);
  }
}

/// `CompanySummary`: the supplier of a product, as the public product schema exposes it.
@immutable
class CompanySummary {
  const CompanySummary({
    required this.id,
    required this.name,
    required this.governorate,
    required this.city,
    required this.website,
    required this.publicEmail,
    required this.phone,
  });

  factory CompanySummary.fromJson(Object? json) {
    final r = JsonReader.of(json, 'CompanySummary');
    return CompanySummary(
      id: r.string('id'),
      name: r.string('name'),
      governorate: r.optional('governorate', Place.fromJson),
      city: r.optional('city', Place.fromJson),
      website: r.stringOr('website'),
      publicEmail: r.stringOr('public_email'),
      phone: r.stringOr('phone'),
    );
  }

  final String id;
  final String name;
  final Place? governorate;
  final Place? city;
  final String website;
  final String publicEmail;
  final String phone;
}

/// A marketplace product: `ProductPublic` (provider catalogue, carries the supplier) or
/// `ProductOwner` (the company's own view, carries `is_active`). The price is the backend's decimal
/// string; `null` means "price on request".
@immutable
class Product {
  const Product({
    required this.id,
    required this.title,
    required this.description,
    required this.brand,
    required this.modelName,
    required this.price,
    required this.currency,
    required this.category,
    required this.createdAt,
    this.company,
    this.isActive,
  });

  factory Product.fromPublicJson(Object? json) {
    final r = JsonReader.of(json, 'ProductPublic');
    return Product._parse(
      r,
      company: CompanySummary.fromJson(r.raw('company')),
    );
  }

  factory Product.fromOwnerJson(Object? json) {
    final r = JsonReader.of(json, 'ProductOwner');
    return Product._parse(r, isActive: r.boolean('is_active'));
  }

  factory Product._parse(
    JsonReader r, {
    CompanySummary? company,
    bool? isActive,
  }) => Product(
    id: r.string('id'),
    title: r.string('title'),
    description: r.stringOr('description'),
    brand: r.stringOr('brand'),
    modelName: r.stringOr('model_name'),
    price: r.stringOrNull('price'),
    currency: r.stringOr('currency'),
    category: ProductCategory.fromJson(r.raw('category')),
    createdAt: r.instant('created_at'),
    company: company,
    isActive: isActive,
  );

  final String id;
  final String title;
  final String description;
  final String brand;
  final String modelName;
  final String? price;
  final String currency;
  final ProductCategory category;
  final DateTime createdAt;

  /// Public products only.
  final CompanySummary? company;

  /// Owner products only.
  final bool? isActive;

  @override
  String toString() => 'Product';
}

/// `CompanyDashboard`: counts computed by the backend; no sales, stock or revenue exist.
@immutable
class CompanyDashboard {
  const CompanyDashboard({
    required this.verificationStatus,
    required this.canPublish,
    required this.total,
    required this.active,
    required this.inactive,
    required this.exposable,
  });

  factory CompanyDashboard.fromJson(Object? json) {
    final r = JsonReader.of(json, 'CompanyDashboard');
    return CompanyDashboard(
      verificationStatus: r.string('verification_status'),
      canPublish: r.boolean('can_publish'),
      total: r.integer('products_total'),
      active: r.integer('products_active'),
      inactive: r.integer('products_inactive'),
      exposable: r.integer('products_exposable'),
    );
  }

  final String verificationStatus;
  final bool canPublish;
  final int total;
  final int active;
  final int inactive;
  final int exposable;
}
