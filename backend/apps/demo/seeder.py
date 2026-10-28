"""Builds the synthetic demo ecosystem (docs/DEMO_DATA.md, ADR-063).

Rules this module follows:
* only models and services that already exist; no business logic is changed or bypassed silently.
  Where a service enforces a commercial limit that a demo must not be subject to (plan quotas for
  publishing jobs and applying), rows are written directly with the same shape the service writes
  and the reason is stated at that call;
* every inserted row is recorded by `Registry` (including side effects) so `clear_demo_data` can
  remove exactly it; every named object has a stable key so a second run is a no-op;
* each phase is ONE transaction that contains the phase's rows, the rows its deferred
  `transaction.on_commit` hooks create (notifications, push hints, ...) and the registry rows that
  own all of them. The hooks are the product's own callbacks, run by the seeder at the end of the
  phase's transaction instead of after its commit, so they see the same data and create the same
  rows. Consequently a phase is either committed together with its ownership records or not at
  all: an interrupted seed (exception, lost connection, killed process) never leaves an
  unregistered demo row behind, and every phase before it stays registered and clearable.
"""

# ruff: noqa: B023 - the factories given to Registry.ensure run immediately, in the same loop turn

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.hashers import make_password
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.chat import services as chat_services
from apps.geography.models import City, Governorate
from apps.jobs import services as jobs_services
from apps.jobs.models import (
    Education,
    JobApplication,
    JobApplicationTransition,
    JobPost,
    JobPostTransition,
    JobSeekerProfile,
    LanguageSkill,
    RecruitmentMessage,
    Skill,
    WorkExperience,
)
from apps.marketplace.models import MedicalCompany, Product, ProductAudience, ProductCategory
from apps.notifications.models import Notification
from apps.offers import services as offers_services
from apps.providers.models import ProviderMembership, ProviderProfile, ServiceOffering
from apps.providers.types import MembershipSide, MembershipStatus, VerificationStatus
from apps.real_estate.models import ListingSuitableUse, PropertyListing, RealEstateSeller
from apps.real_estate.types import ContactMethod, PublicationStatus
from apps.reservations import hooks as reservation_hooks
from apps.reservations import services as reservation_services
from apps.reservations.models import (
    AvailabilitySlot,
    Reservation,
    ReservationTransition,
)
from apps.reservations.types import ReservationStatus
from apps.reviews import services as review_services
from apps.specialties.models import Specialty

from .content import common, estate, jobs, market, people, providers
from .models import DemoRecord
from .registry import Registry

BAGHDAD = ZoneInfo("Asia/Baghdad")
SLOT_TIMES = [time(9, 30), time(11, 0), time(17, 0)]


def _stable(text: str, modulo: int) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest(), 16) % modulo


class DemoSeeder:
    def __init__(self, *, password: str, stdout=None, now: datetime | None = None) -> None:
        self.registry = Registry()
        self.now = now or timezone.now()
        self.stdout = stdout
        self.password_hash = make_password(password)
        self.accounts: dict[str, Account] = {}
        self.provider_profiles: dict[str, ProviderProfile] = {}
        self.companies: dict[str, MedicalCompany] = {}
        self.employers: dict = {}
        self.seekers: dict[str, JobSeekerProfile] = {}
        self.jobs_by_index: dict[int, JobPost] = {}
        self._gov: dict[str, Governorate] = {}
        self._city: dict[tuple[str, str], City] = {}
        self._spec: dict[str, Specialty] = {}
        self.warnings: list[str] = []

    # -- plumbing -----------------------------------------------------------------------------
    def log(self, message: str) -> None:
        if self.stdout is not None:
            self.stdout.write(message)

    def run(self) -> Counter:
        self._load_reference()
        phases = [
            ("accounts, providers and facilities", self.phase_providers),
            ("availability, reservations, reviews, offers, chat", self.phase_care),
            ("marketplace", self.phase_marketplace),
            ("jobs and recruitment", self.phase_jobs),
            ("real estate", self.phase_real_estate),
        ]
        with self.registry:
            for title, phase in phases:
                self.log(f"  {title} ...")
                try:
                    # One transaction per phase: its rows, the rows its deferred hooks create and
                    # the registry rows that own them commit together or not at all (ADR-063).
                    with transaction.atomic():
                        start = len(connection.run_on_commit)
                        phase()
                        self._run_deferred_hooks(start)
                        self.registry.flush()
                except Exception:
                    self.registry.discard_pending()
                    raise
            with transaction.atomic():
                self._polish_notifications()  # updates registered rows only; inserts nothing
        return self.summary()

    def _run_deferred_hooks(self, start: int) -> None:
        """Run the `on_commit` callbacks registered since `start`, inside the phase transaction.

        These are the product's own deferred side effects (reservation/chat events -> notification
        rows -> push hints). Running them before the phase commits lets the registry record the rows
        they insert and commit those records with them. Callbacks that register further callbacks
        are drained too. A `robust` callback failure is logged and skipped, as Django does after a
        real commit; any other failure aborts (and rolls back) the whole phase.
        """
        while len(connection.run_on_commit) > start:
            pending = connection.run_on_commit[start:]
            del connection.run_on_commit[start:]
            for _sids, func, robust in pending:
                if not robust:
                    func()
                    continue
                try:
                    func()
                except Exception as exc:  # noqa: BLE001 - mirrors Django's robust on_commit
                    self.warnings.append(f"a deferred side effect failed and was skipped: {exc!r}")

    def summary(self) -> Counter:
        counts = Counter()
        for label in DemoRecord.objects.values_list("model_label", flat=True).iterator():
            counts[label] += 1
        return counts

    def _load_reference(self) -> None:
        for gov in Governorate.objects.all():
            self._gov[gov.slug] = gov
        for city in City.objects.select_related("governorate"):
            self._city[(city.governorate.slug, city.slug)] = city
        for spec in Specialty.objects.all():
            self._spec[spec.slug] = spec
        if not self._gov:
            raise RuntimeError("No governorates found: run `manage.py migrate` first.")

    def _place(self, gov: str, city: str | None):
        return self._gov[gov], self._city.get((gov, city)) if city else None

    # -- accounts -----------------------------------------------------------------------------
    def _account(self, key: str, role: str, full_name: str, language: str = "ar", phone_n=None):
        def make():
            account = Account.objects.create_user(
                common.email(key),
                password=None,
                full_name=full_name,
                role=role,
                preferred_language=language,
                phone_number=common.phone(phone_n) if phone_n else "",
            )
            account.password = self.password_hash  # one shared hash: hashing 90 accounts is slow
            account.email_verified_at = self.now
            account.save(update_fields=["password", "email_verified_at", "updated_at"])
            return account

        account, _ = self.registry.ensure(f"account:{key}", make)
        self.accounts[key] = account
        return account

    # -- providers and facilities ---------------------------------------------------------------
    def _specs(self, slugs):
        found = [self._spec[s] for s in slugs if s in self._spec]
        missing = [s for s in slugs if s not in self._spec]
        if missing:
            self.warnings.append(f"specialties not found (skipped): {', '.join(missing)}")
        return found

    def _services(self, profile: ProviderProfile, services, specialty=None) -> None:
        for n, (title_ar, title_en, price, minutes) in enumerate(services):
            self.registry.ensure(
                f"service:{profile.pk}:{n}",
                lambda t=(title_ar, title_en), p=price, m=minutes: ServiceOffering.objects.create(
                    provider=profile,
                    title=common.bilingual(*t),
                    description="",
                    specialty=specialty,
                    price=Decimal(p),
                    currency="IQD",
                    duration_minutes=m,
                    is_active=True,
                ),
            )

    def _provider(self, key, ptype, display, about, gov, city, address, spec_slugs, services, n):
        account = self._account(key, AccountRole.PROVIDER, display.split(" | ")[0], phone_n=n)
        governorate, city_obj = self._place(gov, city)

        def make():
            profile = ProviderProfile.objects.create(
                account=account,
                provider_type=ptype,
                display_name=display,
                about=about,
                phone=common.phone(n),
                public_email=common.email(f"info-{key}"),
                governorate=governorate,
                city=city_obj,
                address=address,
                verification_status=VerificationStatus.VERIFIED,
                verification_note="Demo data: verified for presentation.",
                verified_at=self.now,
                verification_changed_at=self.now,
                is_visible=True,
            )
            profile.specialties.set(self._specs(spec_slugs))
            return profile

        profile, _ = self.registry.ensure(f"provider:{key}", make)
        self.provider_profiles[key] = profile
        primary = self._spec.get(spec_slugs[0]) if spec_slugs else None
        self._services(profile, services, primary)
        return profile

    def phase_providers(self) -> None:
        n = 100
        for (
            key,
            ptype,
            name_ar,
            name_en,
            gov,
            city,
            address,
            specs,
            blurbs,
            services,
        ) in providers.FACILITIES:
            n += 1
            self._provider(
                key,
                ptype,
                common.bilingual(name_ar, name_en),
                common.about(blurbs[0], blurbs[1]),
                gov,
                city,
                address,
                specs,
                services,
                n,
            )
        for row in providers.PRACTITIONERS:
            n += 1
            key, a_first, a_family, e_first, e_family, ptype, spec, gov, city, years, langs, fac = (
                row
            )
            ar_bio, en_bio, services = providers.SPECIALTY_PROFILE[spec]
            prefix_ar, prefix_en = {
                "DOCTOR": ("د.", "Dr."),
                "THERAPIST": ("أ.", ""),
                "NURSE": ("الممرض/ة", "Nurse"),
            }[ptype]
            display = common.bilingual(
                f"{prefix_ar} {a_first} {a_family}",
                f"{prefix_en} {e_first} {e_family}".strip(),
            )
            langs_ar = (
                langs.replace("Arabic", "العربية")
                .replace("English", "الإنجليزية")
                .replace("Kurdish", "الكردية")
            )
            about = common.about(
                f"{ar_bio} خبرة {years} سنة. اللغات: {langs_ar}.",
                f"{en_bio} {years} years of experience. Languages: {langs}.",
            )
            profile = self._provider(key, ptype, display, about, gov, city, "", [spec], services, n)
            if fac and fac in self.provider_profiles:
                self._membership(profile, self.provider_profiles[fac], spec)

    def _membership(self, practitioner, facility, spec) -> None:
        title_ar, title_en = providers.MEMBERSHIP_TITLE.get(
            spec, providers.MEMBERSHIP_TITLE["default"]
        )
        self.registry.ensure(
            f"membership:{practitioner.pk}:{facility.pk}",
            lambda: ProviderMembership.objects.create(
                practitioner=practitioner,
                facility=facility,
                status=MembershipStatus.ACTIVE,
                initiated_by=MembershipSide.FACILITY,
                role_title=title_en,
                responded_at=self.now - timedelta(days=60),
                joined_at=self.now - timedelta(days=60),
            ),
        )

    # -- availability, reservations, reviews, offers, chat ----------------------------------------
    def _patients(self) -> list[Account]:
        out = []
        for i, (key, name, lang) in enumerate(people.PATIENTS):
            out.append(self._account(key, AccountRole.PATIENT, name, lang, phone_n=300 + i))
        return out

    def _first_service(self, profile: ProviderProfile) -> ServiceOffering:
        return profile.services.filter(is_active=True).order_by("title").first()

    def _slot_starts(self, day_offset: int, count: int):
        day = (self.now.astimezone(BAGHDAD) + timedelta(days=day_offset)).date()
        for t in SLOT_TIMES[:count]:
            yield datetime.combine(day, t, tzinfo=BAGHDAD)

    def _make_slots(self) -> None:
        """Future appointment slots for the providers that appear in the review plan."""
        for pkey in people.REVIEW_PLAN:
            profile = self.provider_profiles[pkey]
            service = ProviderProfile.objects.get(pk=profile.pk).services.order_by("title").first()
            made = 0
            for offset in range(2, 14):
                starts_list = list(self._slot_starts(offset, 3 if (offset + len(pkey)) % 2 else 2))
                if (self.now.astimezone(BAGHDAD) + timedelta(days=offset)).weekday() == 4:
                    continue  # Friday
                for starts_at in starts_list:
                    if made >= 14:
                        break
                    key = f"slot:{profile.pk}:{starts_at.strftime('%Y%m%d%H%M')}"
                    self.registry.ensure(
                        key,
                        lambda s=starts_at: reservation_services.create_availability_slot(
                            profile, service_id=service.pk, starts_at=s
                        ),
                    )
                    made += 1

    def _free_slot(self, profile: ProviderProfile, index: int):
        slots = list(
            AvailabilitySlot.objects.filter(
                provider=profile, is_active=True, starts_at__gt=self.now + timedelta(hours=36)
            )
            .exclude(reservations__status__in=["PENDING", "CONFIRMED"])
            .order_by("starts_at")[:30]
        )
        return slots[index % len(slots)] if slots else None

    def _book_upcoming(self, patient: Account, pkey: str, action: str, index: int):
        profile = self.provider_profiles[pkey]

        def make():
            slot = self._free_slot(profile, index)
            if slot is None:
                raise RuntimeError(f"no free slot for {pkey}")
            reservation = reservation_services.create_reservation(
                patient=patient,
                slot_id=slot.pk,
                patient_note=people.PATIENT_NOTES[index % len(people.PATIENT_NOTES)],
            )
            if action == "confirm":
                reservation_services.transition_as_provider(
                    reservation.pk,
                    provider=profile,
                    actor=profile.account,
                    target_status=ReservationStatus.CONFIRMED,
                )
            elif action == "cancel":
                reservation_services.cancel_as_patient(
                    reservation.pk, patient=patient, reason="تغيّر في جدول المواعيد"
                )
            reservation.refresh_from_db()
            return reservation

        reservation, _ = self.registry.ensure(f"reservation:up:{patient.email}:{pkey}", make)
        return reservation

    def _past_reservation(self, patient, pkey, tag, days_ago, status, rating=None):
        profile = self.provider_profiles[pkey]
        service = self._first_service(profile)
        starts_at = (
            (self.now - timedelta(days=days_ago))
            .astimezone(BAGHDAD)
            .replace(
                hour=9 + _stable(tag, 9),
                minute=(0, 30)[_stable(tag + "m", 2)],
                second=0,
                microsecond=0,
            )
        )
        ends_at = starts_at + timedelta(minutes=service.duration_minutes)

        def make():
            reservation = Reservation.objects.create(
                patient=patient,
                provider=profile,
                service=service,
                availability_slot=None,
                provider_name_snapshot=profile.display_name,
                service_title_snapshot=service.title,
                price_snapshot=service.price,
                currency_snapshot=service.currency,
                duration_minutes_snapshot=service.duration_minutes,
                starts_at=starts_at,
                ends_at=ends_at,
                status=status,
                status_changed_at=ends_at,
                patient_note="",
            )
            path = {
                ReservationStatus.COMPLETED: [
                    ("", ReservationStatus.PENDING, patient),
                    (ReservationStatus.PENDING, ReservationStatus.CONFIRMED, profile.account),
                    (ReservationStatus.CONFIRMED, ReservationStatus.COMPLETED, profile.account),
                ],
                ReservationStatus.NO_SHOW: [
                    ("", ReservationStatus.PENDING, patient),
                    (ReservationStatus.PENDING, ReservationStatus.CONFIRMED, profile.account),
                    (ReservationStatus.CONFIRMED, ReservationStatus.NO_SHOW, profile.account),
                ],
                ReservationStatus.REJECTED: [
                    ("", ReservationStatus.PENDING, patient),
                    (ReservationStatus.PENDING, ReservationStatus.REJECTED, profile.account),
                ],
            }[status]
            created = []
            for step, (frm, to, actor) in enumerate(path):
                row = ReservationTransition.objects.create(
                    reservation=reservation, actor=actor, from_status=frm, to_status=to
                )
                created.append(row.pk)
                when = starts_at - timedelta(days=2 - min(step, 2) * 0.5)
                ReservationTransition.objects.filter(pk=row.pk).update(created_at=when)
            Reservation.objects.filter(pk=reservation.pk).update(
                created_at=starts_at - timedelta(days=3)
            )
            if rating is not None:
                review = review_services.create_review(
                    patient=patient,
                    reservation_id=reservation.pk,
                    rating=rating,
                    comment=people.REVIEW_COMMENTS[rating][
                        _stable(tag, len(people.REVIEW_COMMENTS[rating]))
                    ],
                )
                type(review).objects.filter(pk=review.pk).update(
                    created_at=ends_at + timedelta(days=1)
                )
            reservation.refresh_from_db()
            return reservation

        reservation, created = self.registry.ensure(f"reservation:past:{tag}", make)
        return reservation, created

    def phase_care(self) -> None:
        patients = self._patients()
        by_key = {a.email.split("@")[0]: a for a in patients}
        self._make_slots()

        # Completed, reviewed visits: ratings vary on purpose (docs/DEMO_DATA.md).
        recent_by_patient: dict[str, list] = {}
        for p_index, (pkey, ratings) in enumerate(people.REVIEW_PLAN.items()):
            for i, rating in enumerate(ratings):
                patient = patients[(p_index + i) % len(patients)]
                days_ago = 5 + (p_index * 7 + i * 19) % 80
                reservation, created = self._past_reservation(
                    patient, pkey, f"{pkey}:{i}", days_ago, ReservationStatus.COMPLETED, rating
                )
                recent_by_patient.setdefault(patient.email, []).append((days_ago, reservation))
        # a few visits with other outcomes
        self._past_reservation(
            by_key["patient-hassan"], "dr-wissam-hilli", "noshow:1", 12, ReservationStatus.NO_SHOW
        )
        self._past_reservation(
            by_key["patient-ali"], "dr-bilal-dulaimi", "rejected:1", 20, ReservationStatus.REJECTED
        )

        # Upcoming bookings through the real services (these emit real notifications).
        plan = [
            ("patient-sara", "dr-mariam-zubaidi", "confirm"),
            ("patient-ali", "dr-karim-saadi", "confirm"),
            ("patient-fatima", "dr-amal-khazraji", "confirm"),
            ("patient-omar", "dr-sarmad-azzawi", "confirm"),
            ("patient-zainab", "th-layla-nuaimi", "pending"),
            ("patient-sara", "dr-huda-rubaie", "confirm"),
            ("patient-ali", "dr-rana-obaidi", "pending"),
            ("patient-hassan", "dr-dalia-tamimi", "confirm"),
            ("patient-zainab", "dr-reem-ani", "cancel"),
            ("patient-omar", "dr-haider-moussawi", "pending"),
            ("patient-fatima", "dr-sura-kubaisi", "confirm"),
            ("patient-hassan", "nr-hanan-saidi", "pending"),
            ("patient-zainab", "nakheel-dental", "pending"),
            ("patient-hassan", "dijla-hospital", "confirm"),
            ("patient-fatima", "fayhaa-center", "confirm"),
            ("patient-sara", "baghdad-imaging", "confirm"),
        ]
        reservations = {}
        for i, (patient_key, pkey, action) in enumerate(plan):
            reservations[(patient_key, pkey)] = self._book_upcoming(
                by_key[patient_key], pkey, action, i
            )

        # Notifications for a few recent completed visits too (the booking ones exist already).
        for items in recent_by_patient.values():
            for _days_ago, reservation in sorted(items, key=lambda x: x[0])[:2]:
                reservation_hooks.emit_created(reservation)
                reservation_hooks.emit_status_changed(
                    reservation, previous_status=ReservationStatus.CONFIRMED, actor=None
                )

        # Conversations (reservation context, exactly as the product allows).
        for patient_key, pkey, lines in people.CHATS:
            reservation = reservations.get((patient_key, pkey))
            if reservation is None or reservation.status == ReservationStatus.CANCELLED:
                continue
            patient = by_key[patient_key]
            provider_account = self.provider_profiles[pkey].account
            self.registry.ensure(
                f"chat:{patient_key}:{pkey}",
                lambda r=reservation, p=patient, pa=provider_account, ls=lines: self._chat(
                    r, p, pa, ls
                ),
            )

        # Offers (existing service; price must be below the service price).
        for pkey, offers in people.OFFERS.items():
            profile = self.provider_profiles[pkey]
            service = self._first_service(profile)
            for n, (title_ar, title_en, discount, days) in enumerate(offers):
                price = (service.price * Decimal(str(1 - discount))).quantize(Decimal("1000"))
                self.registry.ensure(
                    f"offer:{pkey}:{n}",
                    lambda t=(title_ar, title_en), pr=price, d=days: offers_services.create_offer(
                        profile,
                        service_id=service.pk,
                        title=common.bilingual(*t),
                        description="عرض توضيحي لأغراض العرض فقط. | Demonstration offer.",
                        offer_price=pr,
                        starts_at=self.now - timedelta(days=1),
                        ends_at=self.now + timedelta(days=d),
                    ),
                )

    def _chat(self, reservation, patient, provider_account, lines):
        conversation, _ = chat_services.get_or_create_reservation_conversation(
            reservation.pk, actor=patient
        )
        for side, text in lines:
            sender = patient if side == "patient" else provider_account
            chat_services.send_message(conversation.pk, sender=sender, body=text)
        # the patient has read everything; the provider's last reply is still unread for the patient
        # on one conversation, so the unread badges are not all zero in the demo
        last = conversation.__class__.objects.get(pk=conversation.pk).last_sequence
        chat_services.mark_read(conversation.pk, account=provider_account, through_sequence=last)
        if lines[-1][0] == "patient" or _stable(str(conversation.pk), 2):
            chat_services.mark_read(conversation.pk, account=patient, through_sequence=last)
        return conversation

    def _polish_notifications(self) -> None:
        """Spread notification timestamps over the days around the visit and mark older ones read.

        Only rows whose recipient is a registered demo account are touched.
        """
        demo_account_pks = [
            pk
            for pk in DemoRecord.objects.filter(model_label="accounts.Account").values_list(
                "object_pk", flat=True
            )
        ]
        reservations = {
            str(r.pk): r
            for r in Reservation.objects.filter(patient__pk__in=demo_account_pks).only(
                "pk", "starts_at", "status_changed_at", "created_at"
            )
        }
        for note in Notification.objects.filter(recipient__pk__in=demo_account_pks):
            reservation = reservations.get(str(note.resource_id))
            if reservation is None:
                continue
            when = (
                reservation.created_at
                if note.event_type == "RESERVATION_CREATED"
                else (reservation.status_changed_at)
            )
            when = min(when, self.now)
            read_at = when + timedelta(hours=3) if (self.now - when) > timedelta(days=2) else None
            Notification.objects.filter(pk=note.pk).update(created_at=when, read_at=read_at)

    # -- marketplace --------------------------------------------------------------------------
    def phase_marketplace(self) -> None:
        categories = {}
        for n, (slug, name_ar, name_en, audience) in enumerate(market.CATEGORIES):
            existing = ProductCategory.objects.filter(slug=slug).first()
            registered = DemoRecord.objects.filter(
                model_label="marketplace.ProductCategory",
                object_pk=str(getattr(existing, "pk", "")),
            ).exists()
            if existing is not None and not registered:
                categories[slug] = existing  # a real category with this slug: reuse, never own
                continue
            category, created = self.registry.ensure(
                f"category:{slug}",
                lambda s=slug, a=name_ar, e=name_en, i=n: ProductCategory.objects.create(
                    slug=s, name_ar=a, name_en=e, sort_order=900 + i, is_active=True
                ),
            )
            categories[slug] = category
            if created:
                for ptype in audience:
                    ProductAudience.objects.create(category=category, provider_type=ptype)
        for n, row in enumerate(market.COMPANIES):
            key, name_ar, name_en, kind, gov, city, desc_ar, desc_en = row
            account = self._account(
                f"company-{key}",
                AccountRole.MEDICAL_COMPANY,
                common.bilingual(name_ar, name_en)[:150],
                phone_n=500 + n,
            )
            governorate, city_obj = self._place(gov, city)
            company, _ = self.registry.ensure(
                f"company:{key}",
                lambda: MedicalCompany.objects.create(
                    account=account,
                    name=common.bilingual(name_ar, name_en),
                    description=common.about(desc_ar, desc_en),
                    phone=common.phone(500 + n),
                    public_email=common.email(f"sales-{key}"),
                    governorate=governorate,
                    city=city_obj,
                    address="",
                    verification_status="VERIFIED",
                    verification_note="Demo data: verified for presentation.",
                    verified_at=self.now,
                    verification_changed_at=self.now,
                ),
            )
            self.companies[key] = company
        for n, row in enumerate(market.PRODUCTS):
            ckey, cat, title_ar, title_en, brand, model_name, price, desc_ar, desc_en = row
            company = self.companies[ckey]
            self.registry.ensure(
                f"product:{n}",
                lambda: Product.objects.create(
                    company=company,
                    category=categories[cat],
                    title=common.bilingual(title_ar, title_en),
                    description=(
                        f"{desc_ar}\n{desc_en}\n{common.DEMO_NOTE_AR} {common.DEMO_NOTE_EN}"
                    ),
                    brand=brand,
                    model_name=model_name,
                    price=Decimal(price) if price is not None else None,
                    currency="IQD",
                    is_active=True,
                ),
            )

    # -- jobs ---------------------------------------------------------------------------------
    def _employer(self, row, n):
        key, owner_kind, org_type, desc_ar, desc_en = row
        if owner_kind == "facility":
            profile = self.provider_profiles[key]
            account, name = profile.account, profile.display_name
            governorate, city = profile.governorate, profile.city
            link = profile
        else:
            company = self.companies[key]
            account, name = company.account, company.name
            governorate, city = company.governorate, company.city
            link = None

        def make():
            employer = jobs_services.create_employer(
                account,
                name=name,
                organization_type=org_type,
                description=common.about(desc_ar, desc_en),
                governorate=governorate,
                city=city,
                provider_profile=link,
            )
            employer.verification_status = "VERIFIED"
            employer.verification_note = "Demo data: verified for presentation."
            employer.verified_at = self.now
            employer.save(
                update_fields=[
                    "verification_status",
                    "verification_note",
                    "verified_at",
                    "updated_at",
                ]
            )
            return employer

        employer, _ = self.registry.ensure(f"employer:{key}", make)
        self.employers[key] = employer
        return employer

    def phase_jobs(self) -> None:
        for n, row in enumerate(jobs.EMPLOYERS):
            self._employer(row, n)
        today = self.now.astimezone(BAGHDAD).date()
        for n, row in enumerate(jobs.JOBS):
            (
                ekey,
                t_ar,
                t_en,
                profession,
                spec,
                degree,
                exp,
                gov,
                city,
                emp_type,
                mode,
                shift,
                s_min,
                s_max,
                openings,
                status,
                deadline_days,
                d_ar,
                d_en,
                r_ar,
                r_en,
            ) = row
            employer = self.employers[ekey]
            governorate, city_obj = self._place(gov, city)

            def make(row=row, n=n):
                published = status in ("PUBLISHED", "CLOSED")
                age = 1 + (n * 5) % 24
                job = JobPost.objects.create(
                    employer=employer,
                    created_by=employer.created_by,
                    title=common.bilingual(t_ar, t_en),
                    profession=profession,
                    general_specialty=self._spec.get(spec) if spec else None,
                    description=f"{d_ar}\n\n{d_en}\n\n{common.DEMO_NOTE_AR} {common.DEMO_NOTE_EN}",
                    requirements=f"{r_ar}\n{r_en}",
                    minimum_degree=degree,
                    minimum_experience_years=exp,
                    governorate=governorate,
                    city=city_obj,
                    employment_type=emp_type,
                    work_mode=mode,
                    shift_type=shift,
                    salary_min=Decimal(s_min) if s_min else None,
                    salary_max=Decimal(s_max) if s_max else None,
                    salary_currency="IQD",
                    salary_visible=bool(s_min) and n % 3 != 0,
                    number_of_openings=openings,
                    application_deadline=today + timedelta(days=deadline_days)
                    if deadline_days
                    else None,
                    status=status,
                    is_featured=False,
                    submitted_at=self.now - timedelta(days=age + 1) if status != "DRAFT" else None,
                    published_at=self.now - timedelta(days=age) if published else None,
                    closed_at=self.now - timedelta(days=2) if status == "CLOSED" else None,
                )
                path = {
                    "DRAFT": [],
                    "PENDING_ADMIN_REVIEW": [("", "DRAFT"), ("DRAFT", "PENDING_ADMIN_REVIEW")],
                    "PUBLISHED": [
                        ("", "DRAFT"),
                        ("DRAFT", "PENDING_ADMIN_REVIEW"),
                        ("PENDING_ADMIN_REVIEW", "PUBLISHED"),
                    ],
                    "CLOSED": [
                        ("", "DRAFT"),
                        ("DRAFT", "PENDING_ADMIN_REVIEW"),
                        ("PENDING_ADMIN_REVIEW", "PUBLISHED"),
                        ("PUBLISHED", "CLOSED"),
                    ],
                }[status]
                for frm, to in path:
                    JobPostTransition.objects.create(
                        job=job, from_status=frm, to_status=to, actor=employer.created_by
                    )
                return job

            job, _ = self.registry.ensure(f"job:{n}", make)
            self.jobs_by_index[n] = job
        self._seekers()
        self._applications()

    def _seekers(self) -> None:
        for n, row in enumerate(jobs.SEEKERS):
            (
                key,
                name,
                _en,
                profession,
                spec,
                degree,
                years,
                title,
                gov,
                city,
                availability,
                expected,
                skills,
                languages,
                summary,
            ) = row
            account = self._account(key, AccountRole.PATIENT, name, phone_n=700 + n)
            governorate, city_obj = self._place(gov, city)

            def make():
                profile = JobSeekerProfile.objects.create(
                    account=account,
                    professional_title=title,
                    profession=profession,
                    general_specialty=self._spec.get(spec) if spec else None,
                    degree=degree,
                    institution_name="جامعة بغداد" if n % 2 == 0 else "الجامعة المستنصرية",
                    graduation_year=self.now.year - years - 1,
                    years_of_experience=years,
                    professional_summary=f"{summary}\n{common.DEMO_NOTE_AR}",
                    governorate=governorate,
                    city=city_obj,
                    availability=availability,
                    salary_expectation_min=Decimal(expected),
                    salary_currency="IQD",
                    discoverable_by_employers=n % 3 != 2,
                )
                WorkExperience.objects.create(
                    profile=profile,
                    title=title,
                    organization_name="مؤسسة صحية سابقة (توضيحي)",
                    governorate=governorate,
                    start_date=(self.now - timedelta(days=365 * max(years, 1))).date(),
                    is_current=True,
                    description="خبرة عملية في المجال.",
                )
                Education.objects.create(
                    profile=profile,
                    degree=degree,
                    field_of_study=title,
                    institution_name=profile.institution_name,
                    start_year=profile.graduation_year - 4,
                    end_year=profile.graduation_year,
                )
                for skill in skills:
                    Skill.objects.create(profile=profile, name=skill)
                for language, level in languages:
                    LanguageSkill.objects.create(profile=profile, language=language, level=level)
                return profile

            profile, _ = self.registry.ensure(f"seeker:{key}", make)
            self.seekers[key] = profile

    def _applications(self) -> None:
        paths = {
            "SUBMITTED": [],
            "REVIEWING": ["REVIEWING"],
            "SHORTLISTED": ["REVIEWING", "SHORTLISTED"],
            "INTERVIEW": ["REVIEWING", "SHORTLISTED", "INTERVIEW"],
            "ACCEPTED": ["REVIEWING", "SHORTLISTED", "INTERVIEW", "ACCEPTED"],
            "REJECTED": ["REVIEWING", "REJECTED"],
        }
        for n, (job_index, skey, status, employer_msg, candidate_msg) in enumerate(
            jobs.APPLICATIONS
        ):
            job = self.jobs_by_index[job_index]
            profile = self.seekers[skey]
            employer_account = job.employer.created_by

            def make(job=job, profile=profile, status=status, n=n, e=employer_msg, c=candidate_msg):
                age = timedelta(days=2 + (n * 3) % 20)
                # Written directly (not via apply_to_job): that service charges the seeker's plan
                # quota, a commercial limit a demo is not subject to. Same fields, same snapshot.
                application = JobApplication.objects.create(
                    job=job,
                    job_seeker=profile,
                    status=status,
                    cover_text=jobs.COVER_TEXTS[n % len(jobs.COVER_TEXTS)],
                    snapshot=jobs_services.build_snapshot(profile),
                )
                JobApplication.objects.filter(pk=application.pk).update(submitted_at=self.now - age)
                previous = ""
                for step in ["SUBMITTED", *paths[status]]:
                    JobApplicationTransition.objects.create(
                        application=application,
                        from_status=previous,
                        to_status=step,
                        actor=profile.account if step == "SUBMITTED" else employer_account,
                    )
                    previous = step
                if e:
                    RecruitmentMessage.objects.create(
                        application=application,
                        sender=employer_account,
                        sender_side="EMPLOYER",
                        body=e,
                    )
                if c:
                    RecruitmentMessage.objects.create(
                        application=application,
                        sender=profile.account,
                        sender_side="CANDIDATE",
                        body=c,
                    )
                return application

            self.registry.ensure(f"application:{job_index}:{skey}", make)

    # -- real estate --------------------------------------------------------------------------
    def phase_real_estate(self) -> None:
        sellers = {}
        for n, (key, stype, name, about_ar, about_en) in enumerate(estate.SELLERS):
            account = self._account(key, AccountRole.REAL_ESTATE_SELLER, name, phone_n=900 + n)
            seller, _ = self.registry.ensure(
                f"seller:{key}",
                lambda: RealEstateSeller.objects.create(
                    account=account,
                    seller_type=stype,
                    display_name=name,
                    about=common.about(about_ar, about_en),
                    phone=common.phone(900 + n),
                    public_email=common.email(f"contact-{key}"),
                ),
            )
            sellers[key] = seller
        for n, row in enumerate(estate.LISTINGS):
            (
                skey,
                t_ar,
                t_en,
                ptype,
                txn,
                gov,
                city,
                district,
                area,
                price,
                uses,
                f_ar,
                f_en,
                d_ar,
                d_en,
            ) = row
            governorate, city_obj = self._place(gov, city)

            def make(row=row, n=n):
                listing = PropertyListing.objects.create(
                    seller=sellers[skey],
                    title=common.bilingual(t_ar, t_en),
                    description=f"{d_ar}\n\n{d_en}\n\n{common.DEMO_NOTE_AR} {common.DEMO_NOTE_EN}",
                    property_type=ptype,
                    transaction_type=txn,
                    governorate=governorate,
                    city=city_obj,
                    district=district,
                    area_sqm=Decimal(area),
                    price=Decimal(price),
                    currency="IQD",
                    facilities=f"{f_ar} | {f_en}",
                    contact_method=ContactMethod.PHONE,
                    contact_phone=common.phone(950 + n),
                    publication_status=PublicationStatus.PUBLISHED,
                    published_at=self.now - timedelta(days=1 + (n * 3) % 25),
                    expires_at=self.now + timedelta(days=45 + (n * 4) % 40),
                )
                for use in uses:
                    ListingSuitableUse.objects.create(listing=listing, use=use)
                return listing

            self.registry.ensure(f"listing:{n}", make)
