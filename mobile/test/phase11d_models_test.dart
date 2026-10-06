import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:racheeta_mobile/core/api/json_reader.dart';
import 'package:racheeta_mobile/core/time/instants.dart';
import 'package:racheeta_mobile/features/jobs/data/job_models.dart';
import 'package:racheeta_mobile/features/marketplace/data/marketplace_models.dart';
import 'package:racheeta_mobile/features/real_estate/data/real_estate_models.dart';
import 'package:racheeta_mobile/shared/format/formatters.dart';
import 'package:racheeta_mobile/shared/search/search_query.dart';

import 'support/domain_support.dart';

void main() {
  setUpAll(() async {
    await initializeDateFormatting('en');
    await initializeDateFormatting('ar');
  });

  group('SearchQuery', () {
    test('is compared by value, independent of filter order', () {
      const a = SearchQuery(search: 'icu', filters: {'a': '1', 'b': '2'});
      const b = SearchQuery(search: 'icu', filters: {'b': '2', 'a': '1'});
      expect(a, b);
      expect(a.hashCode, b.hashCode);
      expect(a, isNot(const SearchQuery(search: 'icu')));
      expect(
        a,
        isNot(const SearchQuery(search: 'ICU', filters: {'a': '1', 'b': '2'})),
      );
    });

    test('sends the trimmed text under the backend\'s key and every filter, nothing else', () {
      const q = SearchQuery(search: '  icu ', filters: {'profession': 'NURSE'});
      expect(q.toQuery(searchKey: 'q'), {'q': 'icu', 'profession': 'NURSE'});
      expect(q.toQuery(), {'search': 'icu', 'profession': 'NURSE'});
      expect(const SearchQuery(search: '   ').toQuery(), isEmpty);
      expect(const SearchQuery(search: '   ').isEmpty, isTrue);
    });

    test('withFilter sets and removes; empty and null values remove', () {
      var q = const SearchQuery().withFilter('work_mode', 'REMOTE');
      expect(q.filters, {'work_mode': 'REMOTE'});
      q = q.withFilter('work_mode', '');
      expect(q.filters, isEmpty);
      q = q.withFilter('work_mode', 'HYBRID').withFilter('work_mode', null);
      expect(q.filters, isEmpty);
    });

    test(
      'ordering does not count as a narrowing filter and survives clearing',
      () {
        const q = SearchQuery(
          search: 'x',
          filters: {
            'ordering': '-price',
            'property_type': 'CLINIC',
            'city': '',
          },
        );
        expect(q.activeFilterCount(), 1);
        final cleared = q.cleared();
        expect(cleared.filters, {'ordering': '-price'});
        expect(cleared.search, 'x');
      },
    );

    test('filters are unmodifiable after changes', () {
      final q = const SearchQuery().withFilter('a', '1');
      expect(() => q.filters['b'] = '2', throwsUnsupportedError);
    });
  });

  group('calendar dates', () {
    test('a DATE is the same day with no time or zone', () {
      final day = parseCalendarDate('2026-10-05');
      expect(day, DateTime(2026, 10, 5));
      expect(day.isUtc, isFalse);
      expect(day.hour, 0);
    });

    test('anything that is not YYYY-MM-DD is rejected, never guessed', () {
      for (final bad in [
        '2026-10-05T00:00:00Z',
        '2026-13-01',
        '2026-02-30',
        '05/10/2026',
        '2026-1-5',
        '',
        'tomorrow',
      ]) {
        expect(
          () => parseCalendarDate(bad),
          throwsFormatException,
          reason: bad,
        );
      }
    });

    test('formatting keeps the day in English and Arabic', () {
      final day = DateTime(2026, 10, 5);
      expect(formatCalendarDate(day, 'en'), 'Oct 5, 2026');
      expect(
        formatCalendarDate(day, 'ar'),
        contains('2026').or(contains('٢٠٢٦')),
      );
    });

    test('formatDecimal groups numbers and falls back to the raw text', () {
      expect(formatDecimal('120.50', 'en'), '120.5');
      expect(formatDecimal('1500000', 'en'), '1,500,000');
      expect(formatDecimal('n/a', 'en'), 'n/a');
    });
  });

  group('JsonReader additions', () {
    test('boolean is strict; booleanOr falls back', () {
      final r = JsonReader.of({'a': true, 'b': 'yes'}, 'x');
      expect(r.boolean('a'), isTrue);
      expect(() => r.boolean('b'), throwsFormatException);
      expect(() => r.boolean('missing'), throwsFormatException);
      expect(r.booleanOr('b', fallback: false), isFalse);
      expect(r.booleanOr('missing', fallback: true), isTrue);
    });

    test('calendarDateOrNull: absent/empty is null, malformed is an error', () {
      final r = JsonReader.of({
        'a': '2026-10-05',
        'b': '',
        'c': null,
        'd': '2026-10-05T00:00:00Z',
      }, 'x');
      expect(r.calendarDateOrNull('a'), DateTime(2026, 10, 5));
      expect(r.calendarDateOrNull('b'), isNull);
      expect(r.calendarDateOrNull('c'), isNull);
      expect(r.calendarDateOrNull('zzz'), isNull);
      expect(() => r.calendarDateOrNull('d'), throwsFormatException);
    });
  });

  group('job models', () {
    test(
      'a card parses; the deadline is a calendar date; salary keeps its text',
      () {
        final job = Job.fromCardJson(jobCardJson());
        expect(job.title, 'Staff nurse');
        expect(job.applicationDeadline, DateTime(2026, 10, 5));
        expect(job.salaryMin, '1200000.00');
        expect(job.salaryVisible, isTrue);
        expect(job.hiringName, 'Al Noor Hospital');
        expect(job.isOpen, isNull, reason: 'a card does not carry openness');
      },
    );

    test('the agency\'s hiring organisation wins as "who is hiring"', () {
      final agency = Job.fromCardJson({
        ...jobCardJson(),
        'hiring_employer': null,
        'hiring_organization_name': 'Client Clinic',
      });
      expect(agency.hiringName, 'Client Clinic');
      final named = Job.fromCardJson({
        ...jobCardJson(),
        'hiring_employer': employerJson(name: 'Named Org'),
      });
      expect(named.hiringName, 'Named Org');
    });

    test('a missing deadline is null; a timestamp as deadline is rejected', () {
      expect(
        Job.fromCardJson(jobCardJson(deadline: null)).applicationDeadline,
        isNull,
      );
      expect(
        () => Job.fromCardJson(jobCardJson(deadline: '2026-10-05T00:00:00Z')),
        throwsFormatException,
      );
    });

    test('unknown vocabulary codes are kept as the raw code', () {
      final job = Job.fromCardJson(
        jobCardJson(profession: 'ASTRONAUT', employment: 'GIG'),
      );
      expect(job.profession, 'ASTRONAUT');
      expect(job.employmentType, 'GIG');
    });

    test(
      'missing required fields are a format error, not a silent default',
      () {
        expect(
          () => Job.fromCardJson({...jobCardJson()}..remove('id')),
          throwsFormatException,
        );
        expect(
          () => Job.fromCardJson({...jobCardJson()}..remove('title')),
          throwsFormatException,
        );
        expect(
          () => Job.fromCardJson({...jobCardJson()}..remove('employer')),
          throwsFormatException,
        );
        expect(() => Job.fromCardJson('not an object'), throwsFormatException);
        expect(
          () => Job.fromPublicJson({...jobPublicJson()}..remove('is_open')),
          throwsFormatException,
        );
      },
    );

    test('the employer view carries status and the application count; the public view does not', () {
      final employer = Job.fromEmployerJson(employerJobJson(applications: 7));
      expect(employer.status, 'PUBLISHED');
      expect(employer.applicationsCount, 7);
      final pub = Job.fromPublicJson(jobPublicJson());
      expect(pub.status, isNull);
      expect(pub.isOpen, isTrue);
    });

    test('an application keeps the backend status; the private snapshot is not modelled', () {
      final app = JobApplication.fromJson(applicationJson());
      expect(app.status, 'SUBMITTED');
      expect(app.canWithdraw, isTrue);
      expect(app.submittedAt.isUtc, isTrue);
      expect(app.toString(), isNot(contains('résumé')));
      for (final closed in [
        'ACCEPTED',
        'REJECTED',
        'WITHDRAWN',
        'FUTURE_STATE',
      ]) {
        expect(
          JobApplication.fromJson(applicationJson(status: closed)).canWithdraw,
          isFalse,
          reason: closed,
        );
      }
      expect(
        () => JobApplication.fromJson(
          {...applicationJson()}..remove('submitted_at'),
        ),
        throwsFormatException,
      );
    });

    test('a recruiter dashboard with figures', () {
      final d = RecruiterDashboard.fromJson(recruiterDashboardJson());
      expect(d.organizationName, 'Al Noor Hospital');
      expect(d.myRole, 'RECRUITER');
      expect(d.canRecruit, isTrue);
      expect(d.jobsTotal, 9);
      expect(d.jobsOpenNow, 4);
      expect(d.hasApplicationFigures, isTrue);
      expect(d.applicationsTotal, 31);
      expect(d.applicationsAwaitingReview, 15);
      expect(d.applicationsLast7Days, 8);
      expect(d.interviewsTotal, 6);
      expect(d.seatsActive, 3);
      expect(d.seatsLimit, 5);
    });

    test('withheld application figures stay null, never zero', () {
      final d = RecruiterDashboard.fromJson(
        recruiterDashboardJson(withApplications: false),
      );
      expect(d.applicationsAccess, 'billing_plan_required');
      expect(d.hasApplicationFigures, isFalse);
      expect(d.applicationsTotal, isNull);
      expect(d.interviewsTotal, isNull);
    });

    test('an unlimited seat count is null', () {
      final json = recruiterDashboardJson();
      json['seats'] = {'active_members': 3, 'enabled': true, 'limit': null};
      expect(RecruiterDashboard.fromJson(json).seatsLimit, isNull);
    });

    test('a dashboard missing a required section is a format error', () {
      expect(
        () => RecruiterDashboard.fromJson(
          {...recruiterDashboardJson()}..remove('jobs'),
        ),
        throwsFormatException,
      );
      expect(
        () => RecruiterDashboard.fromJson(
          {...recruiterDashboardJson()}..remove('seats'),
        ),
        throwsFormatException,
      );
    });
  });

  group('marketplace models', () {
    test('a public product has its company; the owner product has the activity flag', () {
      final pub = Product.fromPublicJson(productPublicJson());
      expect(pub.company, isNotNull);
      expect(pub.isActive, isNull);
      final own = Product.fromOwnerJson(productOwnerJson());
      expect(own.isActive, isNotNull);
      expect(own.company, isNull);
    });

    test(
      'the price stays the backend text; an unknown currency is kept as is',
      () {
        final p = Product.fromPublicJson({
          ...productPublicJson(),
          'currency': 'XYZ',
        });
        expect(p.currency, 'XYZ');
        expect(p.price, isA<String?>());
      },
    );

    test('missing required fields are a format error', () {
      expect(
        () => Product.fromPublicJson({...productPublicJson()}..remove('id')),
        throwsFormatException,
      );
      expect(
        () => Product.fromPublicJson({...productPublicJson()}..remove('title')),
        throwsFormatException,
      );
      expect(
        () => ProductCategory.fromJson({...categoryJson()}..remove('slug')),
        throwsFormatException,
      );
    });

    test('the company dashboard counts', () {
      final d = CompanyDashboard.fromJson(companyDashboardJson());
      expect(d.total, greaterThanOrEqualTo(d.active));
      expect(
        () => CompanyDashboard.fromJson(
          {...companyDashboardJson()}..remove('can_publish'),
        ),
        throwsFormatException,
      );
    });
  });

  group('real-estate models', () {
    test(
      'the public listing has a seller summary and no publication status',
      () {
        final l = PropertyListing.fromPublicJson(listingJson());
        expect(l.seller, isNotNull);
        expect(l.publicationStatus, isNull);
        expect(l.areaSqm, '120.50');
        expect(l.price, '150000000.00');
        expect(l.suitableUses, ['CLINIC', 'MEDICAL_CENTER']);
      },
    );

    test('the owner listing carries publication status and visibility', () {
      final l = PropertyListing.fromOwnerJson(ownerListingJson());
      expect(l.publicationStatus, isNotNull);
      expect(l.isPublic, isNotNull);
      expect(l.isExpired, isNotNull);
    });

    test('price on request (null) and unknown codes are kept without inventing values', () {
      final l = PropertyListing.fromPublicJson(
        listingJson(price: null, area: null, propertyType: 'FLYING_CASTLE'),
      );
      expect(l.price, isNull);
      expect(l.areaSqm, isNull);
      expect(l.propertyType, 'FLYING_CASTLE');
    });

    test(
      'contact fields stay exactly what the backend sent (empty when withheld)',
      () {
        final l = PropertyListing.fromPublicJson(
          listingJson(phone: null, email: null),
        );
        expect(l.contactPhone, anyOf(isNull, isEmpty));
        expect(l.contactEmail, anyOf(isNull, isEmpty));
      },
    );

    test(
      'missing required fields are a format error; the dashboard counts parse',
      () {
        expect(
          () =>
              PropertyListing.fromPublicJson({...listingJson()}..remove('id')),
          throwsFormatException,
        );
        expect(
          () => PropertyListing.fromOwnerJson(
            {...ownerListingJson()}..remove('publication_status'),
          ),
          throwsFormatException,
        );
        final d = OwnerDashboard.fromJson(ownerDashboardJson());
        expect(d.total, isNonNegative);
        expect(
          () => OwnerDashboard.fromJson(
            {...ownerDashboardJson()}..remove('listings_total'),
          ),
          throwsFormatException,
        );
      },
    );
  });

  test('instants keep rejecting a timestamp without an offset (11B policy unchanged)', () {
    expect(() => parseInstant('2026-10-05T09:00:00'), throwsFormatException);
    expect(
      parseInstant('2026-10-05T09:00:00+03:00').toUtc(),
      DateTime.utc(2026, 10, 5, 6),
    );
  });
}

extension on Matcher {
  Matcher or(Matcher other) => anyOf(this, other);
}
