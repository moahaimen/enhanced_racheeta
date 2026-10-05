import 'patient_support.dart';

const sellerAccountId = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
const otherSellerAccountId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
const companyAccountId = 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee';
const otherCompanyAccountId = 'ffffffff-ffff-4fff-8fff-ffffffffffff';
const recruiterAccountId = '12121212-1212-4121-8121-121212121212';
const otherRecruiterAccountId = '34343434-3434-4343-8343-343434343434';
const listingId = '55555555-0000-4000-8000-000000000001';

Map<String, Object?> _account(
  String id,
  String name,
  String role,
  List<String> permissions,
) => {
  'id': id,
  'email': '$name@example.test'.toLowerCase().replaceAll(' ', '-'),
  'full_name': name,
  'phone_number': '',
  'role': role,
  'preferred_language': 'ar',
  'email_verified': true,
  'email_verified_at': '2026-09-01T10:00:00Z',
  'has_password': true,
  'is_staff': false,
  'permissions': permissions,
  'created_at': '2026-09-01T09:00:00Z',
  'last_login': null,
};

/// A REAL_ESTATE_SELLER account as `/me` returns it.
Map<String, Object?> sellerAccountJson({
  String id = sellerAccountId,
  String name = 'Seller One',
  List<String>? permissions,
}) => _account(
  id,
  name,
  'REAL_ESTATE_SELLER',
  permissions ??
      [
        'accounts.view_self',
        'accounts.edit_self',
        'real_estate.manage_own_listings',
      ],
);

Map<String, Object?> companyAccountJson({
  String id = companyAccountId,
  String name = 'Company One',
  List<String>? permissions,
}) => _account(
  id,
  name,
  'MEDICAL_COMPANY',
  permissions ??
      [
        'accounts.view_self',
        'accounts.edit_self',
        'marketplace.manage_own_products',
        'advertising.manage_own_campaigns',
      ],
);

/// A recruiter is any account with an employer membership; `/me` carries no recruiter capability,
/// so the app asks the server (`GET /dashboards/`).
Map<String, Object?> recruiterAccountJson({
  String id = recruiterAccountId,
  String name = 'Recruiter One',
}) => _account(id, name, 'PROVIDER', [
  'accounts.view_self',
  'accounts.edit_self',
  'jobs.manage_own',
]);

/// A public `PropertyListingPublic`.
Map<String, Object?> listingJson({
  String id = listingId,
  String title = 'Clinic floor in Karrada',
  String propertyType = 'CLINIC',
  String transaction = 'SALE',
  String? price = '150000000.00',
  String currency = 'IQD',
  String? area = '120.50',
  String district = 'Arasat',
  List<String> uses = const ['CLINIC', 'MEDICAL_CENTER'],
  String? phone = '+9647700000001',
  String? email,
  String contactMethod = 'PHONE',
  String description = 'Ground floor, street frontage.',
  String facilities = 'Parking, elevator',
}) => {
  'id': id,
  'title': title,
  'description': description,
  'property_type': propertyType,
  'transaction_type': transaction,
  'governorate': placeJson('g1', 'بغداد', 'Baghdad'),
  'city': placeJson('c1', 'الكرادة', 'Karrada'),
  'district': district,
  'latitude': '33.312800',
  'longitude': '44.361500',
  'area_sqm': area,
  'price': price,
  'currency': currency,
  'suitable_uses': uses,
  'facilities': facilities,
  'contact_method': contactMethod,
  'contact_phone': phone,
  'contact_email': email,
  'seller': {
    'id': 'seller-1',
    'display_name': 'Layla Estates',
    'seller_type': 'AGENT',
  },
  'published_at': '2026-09-20T10:00:00Z',
  'expires_at': '2026-12-20T10:00:00Z',
  'created_at': '2026-09-20T10:00:00Z',
  'updated_at': '2026-09-20T10:00:00Z',
};

/// A `PropertyListingOwner`.
Map<String, Object?> ownerListingJson({
  String id = listingId,
  String title = 'My clinic floor',
  String status = 'DRAFT',
  bool isPublic = false,
  bool isExpired = false,
  String? price = '90000000.00',
}) => {
  ...listingJson(id: id, title: title, price: price)..remove('seller'),
  'publication_status': status,
  'is_public': isPublic,
  'is_expired': isExpired,
  'contact_phone': '+9647700000001',
  'contact_email': 'owner@example.test',
};

Map<String, Object?> ownerDashboardJson() => {
  'listings_total': 6,
  'listings_draft': 2,
  'listings_published': 4,
  'listings_visible': 3,
  'listings_expired': 1,
  'listings_sale': 4,
  'listings_rent': 2,
};

const productId = '66666666-0000-4000-8000-000000000001';
const providerBrowseId = 'abababab-abab-4bab-8bab-abababababab';
const otherProviderBrowseId = 'cdcdcdcd-cdcd-4dcd-8dcd-cdcdcdcdcdcd';

/// A verified provider's `/me` (the marketplace capability is in the PROVIDER role registry).
Map<String, Object?> browsingProviderJson({
  String id = providerBrowseId,
  String name = 'Dr Browser',
}) => _account(id, name, 'PROVIDER', [
  'accounts.view_self',
  'accounts.edit_self',
  'providers.search',
  'marketplace.view_targeted_products',
]);

Map<String, Object?> categoryJson({
  String id = 'cat-1',
  String ar = 'مستلزمات التشخيص',
  String en = 'Diagnostic supplies',
}) => {
  'id': id,
  'slug': en.toLowerCase().replaceAll(' ', '-'),
  'name_ar': ar,
  'name_en': en,
  'parent_id': null,
  'sort_order': 0,
  'can_publish': true,
};

Map<String, Object?> productPublicJson({
  String id = productId,
  String title = 'Digital thermometer',
  String? price = '25000.00',
  String brand = 'MedTemp',
  String model = 'MT-200',
  Map<String, Object?>? category,
}) => {
  'id': id,
  'title': title,
  'description': 'Fast contactless reading.',
  'brand': brand,
  'model_name': model,
  'price': price,
  'currency': 'IQD',
  'category': category ?? categoryJson(),
  'company': {
    'id': 'company-1',
    'name': 'Al Shifa Supplies',
    'governorate': placeJson('g1', 'بغداد', 'Baghdad'),
    'city': placeJson('c1', 'الكرادة', 'Karrada'),
    'website': 'https://shifa.example.test',
    'public_email': 'sales@shifa.example.test',
    'phone': '+9647700000009',
  },
  'created_at': '2026-09-20T10:00:00Z',
  'updated_at': '2026-09-20T10:00:00Z',
};

Map<String, Object?> productOwnerJson({
  String id = productId,
  String title = 'My thermometer',
  bool active = false,
  String? price = '25000.00',
}) => {
  ...productPublicJson(id: id, title: title, price: price)..remove('company'),
  'is_active': active,
};

Map<String, Object?> companyDashboardJson({
  String status = 'VERIFIED',
  bool canPublish = true,
}) => {
  'verification_status': status,
  'can_publish': canPublish,
  'products_total': 7,
  'products_active': 4,
  'products_inactive': 3,
  'products_exposable': 2,
};

const jobId = '77777777-0000-4000-8000-000000000001';
const applicationId = '88888888-0000-4000-8000-000000000001';

Map<String, Object?> employerJson({String name = 'Al Noor Hospital'}) => {
  'id': 'employer-1',
  'name': name,
  'organization_type': 'HOSPITAL',
  'description': '',
  'governorate': placeJson('g1', 'بغداد', 'Baghdad'),
  'city': placeJson('c1', 'الكرادة', 'Karrada'),
  'is_recruitment_agency': false,
  'is_verified': true,
  'provider_profile_id': '22222222-2222-4222-8222-222222222222',
};

/// A `JobCard` (list item).
Map<String, Object?> jobCardJson({
  String id = jobId,
  String title = 'Staff nurse',
  String profession = 'NURSE',
  String employment = 'FULL_TIME',
  String workMode = 'ON_SITE',
  bool salaryVisible = true,
  String? salaryMin = '1200000.00',
  String? salaryMax = '1800000.00',
  String? deadline = '2026-10-05',
  bool featured = false,
}) => {
  'id': id,
  'title': title,
  'employer': employerJson(),
  'hiring_employer': null,
  'hiring_organization_name': '',
  'profession': profession,
  'general_specialty': {
    'id': 's1',
    'slug': 'nursing',
    'name_ar': 'تمريض',
    'name_en': 'Nursing',
    'parent': null,
  },
  'detailed_specialty': 'ICU',
  'governorate': placeJson('g1', 'بغداد', 'Baghdad'),
  'city': placeJson('c1', 'الكرادة', 'Karrada'),
  'employment_type': employment,
  'work_mode': workMode,
  'shift_type': 'ROTATING',
  'minimum_degree': 'BACHELOR',
  'minimum_experience_years': 2,
  'salary_min': salaryMin,
  'salary_max': salaryMax,
  'salary_currency': 'IQD',
  'salary_visible': salaryVisible,
  'is_featured': featured,
  'published_at': '2026-09-20T10:00:00Z',
  'application_deadline': deadline,
};

/// A `JobPublic` (detail).
Map<String, Object?> jobPublicJson({
  String id = jobId,
  bool isOpen = true,
  String title = 'Staff nurse',
}) => {
  ...jobCardJson(id: id, title: title),
  'description': 'Care for patients in the ICU.',
  'responsibilities': 'Monitor vitals.',
  'requirements': 'Valid licence.',
  'workplace_text': 'Third floor',
  'number_of_openings': 3,
  'is_open': isOpen,
};

/// A `JobEmployer` (the organisation's own view).
Map<String, Object?> employerJobJson({
  String id = jobId,
  String title = 'Staff nurse',
  String status = 'PUBLISHED',
  int applications = 4,
}) => {
  ...jobPublicJson(id: id, title: title),
  'status': status,
  'moderation_note': '',
  'moderation_flags': <Object?>[],
  'featured_until': null,
  'submitted_at': '2026-09-20T09:00:00Z',
  'closed_at': null,
  'applications_count': applications,
  'transitions': <Object?>[],
  'created_at': '2026-09-20T09:00:00Z',
  'updated_at': '2026-09-20T09:00:00Z',
};

Map<String, Object?> applicationJson({
  String id = applicationId,
  String status = 'SUBMITTED',
  String title = 'Staff nurse',
}) => {
  'id': id,
  'job': jobCardJson(title: title),
  'status': status,
  'cover_text': 'I would like to join.',
  'snapshot': {'private': 'résumé data that must never be shown'},
  'submitted_at': '2026-10-02T08:00:00Z',
  'transitions': <Object?>[],
  'interviews': <Object?>[],
};

Map<String, Object?> recruiterDashboardJson({bool withApplications = true}) => {
  'organization': {
    'id': 'employer-1',
    'name': 'Al Noor Hospital',
    'verification_status': 'VERIFIED',
    'recruitment_status': 'ACTIVE',
    'can_recruit': true,
    'my_role': 'RECRUITER',
  },
  'jobs': {
    'total': 9,
    'by_status': {
      'DRAFT': 1,
      'PENDING_ADMIN_REVIEW': 0,
      'PUBLISHED': 5,
      'CLOSED': 2,
      'EXPIRED': 1,
      'REJECTED': 0,
      'SUSPENDED': 0,
      'ARCHIVED': 0,
    },
    'open_now': 4,
  },
  'applications_access': withApplications ? null : 'billing_plan_required',
  'applications': withApplications
      ? {
          'total': 31,
          'by_status': {
            'SUBMITTED': 10,
            'REVIEWING': 5,
            'SHORTLISTED': 4,
            'INTERVIEW': 2,
            'ACCEPTED': 3,
            'REJECTED': 6,
            'WITHDRAWN': 1,
          },
          'awaiting_review': 15,
          'last_7_days': 8,
        }
      : null,
  'interviews': withApplications
      ? {
          'total': 6,
          'by_status': {
            'PROPOSED': 2,
            'ACCEPTED': 3,
            'DECLINED': 1,
            'CANCELLED': 0,
          },
        }
      : null,
  'seats': {'active_members': 3, 'enabled': true, 'limit': 5},
};
