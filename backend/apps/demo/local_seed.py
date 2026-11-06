"""LOCAL-ONLY seed phases (docs/DEMO_DATA.md §Local workspace demo).

Run by `DemoSeeder` only when `DEMO_LOCAL_EXTRAS=1`, which only `seed_local_demo` sets, AFTER
`local_guard` accepted the database. Every phase re-checks the guard itself, so an environment
variable set by mistake on a hosted service still cannot seed these rows there.

Same rules as the base seeder: product services are used wherever they exist (orders, quotes,
promotions, preferences, outreach), rows are registered by the active `Registry`, and every
named object has a stable key so a second run is a no-op.
"""

# ruff: noqa: B023 - the factories given to Registry.ensure run immediately, in the same loop turn

from __future__ import annotations

import os
from datetime import timedelta
from decimal import Decimal

from django.conf import settings

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole, AccountType
from apps.advertising.models import (
    AdvertisingCampaign,
    AdvertisingRate,
    CampaignPayment,
    CampaignProviderType,
    CampaignSpecialty,
)
from apps.advertising.outreach import notify_campaign_audience
from apps.commerce import checkout as store_checkout
from apps.commerce import lifecycle
from apps.commerce import services as commerce
from apps.commerce.models import Checkout, Coupon, Order, ProductOffer, QuoteRequest
from apps.jobs.models import EmployerMembership, JobSeekerProfile
from apps.ledger import settlement
from apps.ledger.models import SettlementBatch
from apps.marketplace.models import MedicalCompany, Product, ProductAudience, ProductCategory
from apps.offers.services import create_offer
from apps.preferences import services as preferences
from apps.preferences.models import MarketingPreference
from apps.providers.models import ProviderProfile, ServiceOffering
from apps.real_estate import promotions
from apps.real_estate.models import ListingPromotion
from apps.workspaces.models import OrganizationMember

from . import local_guard
from .content import common
from .content import local_extras as content
from .models import DemoRecord

PROVIDER_ACCOUNT_TYPE = {
    "DOCTOR": AccountType.DOCTOR,
    "NURSE": AccountType.NURSE,
    "THERAPIST": AccountType.THERAPIST,
    "HOSPITAL": AccountType.HOSPITAL,
    "MEDICAL_CENTER": AccountType.MEDICAL_CENTER,
    "PHARMACY": AccountType.PHARMACY,
    "LABORATORY": AccountType.LABORATORY,
    "BEAUTY_CENTER": AccountType.BEAUTY_CENTER,
}


def enabled() -> bool:
    return os.environ.get("DEMO_LOCAL_EXTRAS") == "1"


def admin_enabled() -> bool:
    return os.environ.get("DEMO_LOCAL_ADMIN") == "1"


class LocalExtras:
    def __init__(self, seeder) -> None:
        self.s = seeder
        self.registry = seeder.registry
        self.products: dict[str, Product] = {}
        self.admin: Account | None = None
        self.finance: Account | None = None

    # -- helpers ------------------------------------------------------------------------------
    def _guard(self) -> None:
        local_guard.assert_local_disposable_database()

    def _get(self, key: str):
        return self.registry.get(key)

    def _provider(self, key: str) -> ProviderProfile:
        return self.s.provider_profiles.get(key) or self._get(f"provider:{key}")

    def _company(self, key: str) -> MedicalCompany:
        return self.s.companies.get(key) or self._get(f"company:{key}")

    def _person(self, key: str, full_name: str, **flags) -> Account:
        account = self.s._account(key, AccountRole.PATIENT, full_name)
        changes = {k: v for k, v in flags.items() if getattr(account, k) != v}
        if changes:
            Account.objects.filter(pk=account.pk).update(**changes)
            account.refresh_from_db()
        return account

    # -- phase 1: people, organizations, preferences ------------------------------------------
    def phase_people(self) -> None:
        self._guard()
        if admin_enabled():
            self._admin()
        for key, name, ptype, spec, status in content.CONTRAST_PROVIDERS:
            account = self.s._account(key, AccountRole.PROVIDER, name.split(" | ")[0])
            governorate, city = self.s._place("baghdad", "baghdad")

            def make():
                profile = ProviderProfile.objects.create(
                    account=account,
                    provider_type=ptype,
                    display_name=name,
                    about=common.about("ملف للمقارنة.", "Contrast profile for testing."),
                    governorate=governorate,
                    city=city,
                    verification_status=status,
                    verification_changed_at=self.s.now,
                    is_visible=True,
                )
                profile.specialties.set(self.s._specs([spec]))
                return profile

            self.s.provider_profiles[key], _ = self.registry.ensure(f"provider:{key}", make)
        for key, name, flag in content.CONTRAST_PATIENTS:
            if flag == "inactive":
                self._person(key, name, is_active=False)
            else:
                self._person(key, name, email_verified_at=None)
        for n, (key, ptype, name_ar, name_en, gov, city, svc) in enumerate(
            content.EXTRA_FACILITIES
        ):
            profile = self.s._provider(
                key,
                ptype,
                common.bilingual(name_ar, name_en),
                common.about("منشأة توضيحية.", "Fictional demo facility."),
                gov,
                city,
                "",
                [],
                [(ar, en, Decimal(price), minutes) for ar, en, price, minutes in svc],
                380 + n,
            )
            for m, (fkey, t_ar, t_en, discount, days) in enumerate(content.EXTRA_FACILITY_OFFERS):
                if fkey != key:
                    continue
                service = ServiceOffering.objects.filter(provider=profile).order_by("title").first()
                price = (service.price * Decimal(str(1 - float(discount)))).quantize(
                    Decimal("1000")
                )
                self.registry.ensure(
                    f"offer:{key}:{m}",
                    lambda t=(t_ar, t_en), pr=price, d=days, sv=service: create_offer(
                        profile,
                        service_id=sv.pk,
                        title=common.bilingual(*t),
                        description="عرض توضيحي. | Demonstration offer.",
                        offer_price=pr,
                        starts_at=self.s.now - timedelta(days=1),
                        ends_at=self.s.now + timedelta(days=d),
                    ),
                )
        for key, name, roles in [*content.STAFF, *content.EXTRA_STAFF]:
            person = self._person(key, name)
            for kind, org_key, role, active in roles:
                org = self._provider(org_key) if kind == "facility" else self._company(org_key)
                fields = {"facility": org} if kind == "facility" else {"company": org}

                def make():
                    return OrganizationMember.objects.create(
                        account=person,
                        role=role,
                        added_by=org.account,
                        status="ACTIVE" if active else "ENDED",
                        ended_at=None if active else self.s.now - timedelta(days=10),
                        **fields,
                    )

                self.registry.ensure(f"orgmember:{key}:{kind}:{org_key}", make)
        for key, name, employer_key in content.RECRUITERS:
            person = self._person(key, name)
            employer = self.s.employers.get(employer_key) or self._get(f"employer:{employer_key}")
            # Direct write (same shape as jobs.services.add_member): a demo must not consume the
            # employer's paid recruiter-seat entitlement.
            self.registry.ensure(
                f"recruiter:{key}",
                lambda: EmployerMembership.objects.create(
                    employer=employer, account=person, role="RECRUITER", status="ACTIVE"
                ),
            )
        for key, name, profession, title, degree, years in content.EXTRA_SEEKERS:
            person = self._person(key, name)
            governorate, city = self.s._place("baghdad", "baghdad")
            self.registry.ensure(
                f"seeker:{key}",
                lambda: JobSeekerProfile.objects.create(
                    account=person,
                    professional_title=title,
                    profession=profession,
                    degree=degree,
                    institution_name="جامعة بغداد",
                    graduation_year=self.s.now.year - years - 1,
                    years_of_experience=years,
                    professional_summary=f"{title}.\n{common.DEMO_NOTE_AR}",
                    governorate=governorate,
                    city=city,
                    availability="IMMEDIATE",
                    salary_currency="IQD",
                    discoverable_by_employers=True,
                ),
            )
        for key, changes in {**content.PREFERENCES, **content.EXTRA_PREFERENCES}.items():
            account = self.s.accounts.get(key) or self._get(f"account:{key}")
            if account is None:
                self.s.warnings.append(f"preference target missing: {key}")
                continue
            if not MarketingPreference.objects.filter(account=account).exists():
                preferences.update(account, changes)

    def _admin(self) -> None:
        password = os.environ.get("DEMO_LOCAL_ADMIN_PASSWORD", "")
        if len(password) < 16:
            raise RuntimeError("DEMO_LOCAL_ADMIN_PASSWORD is required for the local admin.")

        def make():
            return Account.objects.create_superuser(
                common.email("local-admin"),
                password=password,
                full_name="مدير محلي | Local admin",
            )

        self.admin, _ = self.registry.ensure("account:local-admin", make)
        self.finance = self._staff(
            "local-finance", "مسؤول مالية راشيتة | Racheeta finance", password, finance=True
        )
        self._staff(
            "local-support",
            "دعم راشيتة (بلا صلاحية مالية) | Racheeta support",
            password,
            finance=False,
        )

    def _staff(self, key: str, full_name: str, password: str, *, finance: bool) -> Account:
        """A Racheeta staff account that is NOT a superuser. Finance gets exactly one permission
        (ledger.change_settlementbatch); support gets none, to demonstrate the refusal."""
        from django.contrib.auth.models import Permission

        def make():
            account = Account.objects.create_user(
                common.email(key), password=password, full_name=full_name
            )
            Account.objects.filter(pk=account.pk).update(
                role=AccountRole.ADMIN, is_staff=True, email_verified_at=self.s.now
            )
            if finance:
                account.user_permissions.add(
                    Permission.objects.get(codename="change_settlementbatch")
                )
            return Account.objects.get(pk=account.pk)

        account, _ = self.registry.ensure(f"account:{key}", make)
        return account

    def _account_types(self) -> None:
        """Classify demo accounts (onboarding account type) from their CURRENT profiles."""
        pks = DemoRecord.objects.filter(model_label="accounts.Account").values_list(
            "object_pk", flat=True
        )
        accounts = Account.objects.filter(pk__in=list(pks), account_type="")
        for account in accounts.select_related(
            "provider_profile", "medical_company", "real_estate_seller"
        ):
            kind = ""
            if account.role == AccountRole.PATIENT:
                kind = AccountType.PATIENT
            elif account.role == AccountRole.PROVIDER and hasattr(account, "provider_profile"):
                kind = PROVIDER_ACCOUNT_TYPE.get(account.provider_profile.provider_type, "")
            elif account.role == AccountRole.MEDICAL_COMPANY and hasattr(
                account, "medical_company"
            ):
                business = account.medical_company.business_type
                kind = business if business in AccountType.values else ""
            elif account.role == AccountRole.REAL_ESTATE_SELLER and hasattr(
                account, "real_estate_seller"
            ):
                agent = account.real_estate_seller.seller_type == "AGENT"
                kind = AccountType.PROPERTY_AGENT if agent else AccountType.PROPERTY_OWNER
            if kind:
                Account.objects.filter(pk=account.pk).update(account_type=kind)

    # -- phase 2: business classification, store, campaigns ----------------------------------
    def phase_commerce(self) -> None:
        self._guard()
        for key, business in content.COMPANY_BUSINESS_TYPES.items():
            company = self._company(key)
            if company is not None and company.business_type != business:
                MedicalCompany.objects.filter(pk=company.pk).update(business_type=business)
        for n, row in enumerate(content.EXTRA_COMPANIES):
            key, name_ar, name_en, business, status, active, gov, city = row
            account = self.s._account(
                f"company-{key}", AccountRole.MEDICAL_COMPANY, name_en, phone_n=600 + n
            )
            governorate, city_obj = self.s._place(gov, city)
            company, _ = self.registry.ensure(
                f"company:{key}",
                lambda: MedicalCompany.objects.create(
                    account=account,
                    name=common.bilingual(name_ar, name_en),
                    description=common.about("شركة توضيحية.", "Fictional demo business."),
                    governorate=governorate,
                    city=city_obj,
                    business_type=business,
                    verification_status=status,
                    verified_at=self.s.now if status == "VERIFIED" else None,
                    verification_changed_at=self.s.now,
                ),
            )
            if account.is_active != active:
                Account.objects.filter(pk=account.pk).update(is_active=active)
            self.s.companies[key] = company
        categories = {}
        for n, (slug, name_ar, name_en, consumer, audience) in enumerate(content.EXTRA_CATEGORIES):

            def make():
                category = ProductCategory.objects.create(
                    slug=slug,
                    name_ar=name_ar,
                    name_en=name_en,
                    sort_order=950 + n,
                    is_active=True,
                    consumer_allowed=consumer,
                )
                for ptype, spec in audience:
                    ProductAudience.objects.create(
                        category=category,
                        provider_type=ptype,
                        specialty=self.s._spec.get(spec) if spec else None,
                    )
                return category

            categories[slug], _ = self.registry.ensure(f"category:{slug}", make)
        demo_categories = DemoRecord.objects.filter(
            model_label="marketplace.ProductCategory"
        ).values_list("object_pk", flat=True)
        demo_categories = {str(pk) for pk in demo_categories} | {
            str(c.pk) for c in categories.values()
        }  # rows created in this phase are registered only when the phase commits
        for compliance, slugs in content.COMPLIANCE_CLASSES.items():
            ProductCategory.objects.filter(pk__in=list(demo_categories), slug__in=slugs).update(
                compliance_class=compliance
            )
        for row in content.EXTRA_PRODUCTS:
            key, ckey, cat, t_ar, t_en, price, channel, restricted, stock = row
            category = categories.get(cat) or ProductCategory.objects.get(slug=cat)
            company = self._company(ckey)
            self.products[key], _ = self.registry.ensure(
                f"product:local:{key}",
                lambda: Product.objects.create(
                    company=company,
                    category=category,
                    title=common.bilingual(t_ar, t_en),
                    description=f"{common.DEMO_NOTE_AR} {common.DEMO_NOTE_EN}",
                    price=Decimal(price),
                    currency="IQD",
                    is_active=True,
                    sale_channel=channel,
                    is_restricted=restricted,
                    stock_quantity=stock,
                ),
            )
        self._campaigns()
        self._promotions()

    def _promotions(self) -> None:
        """Low-stock levels, coupons (seller- and Racheeta-funded, one expired), product sales."""
        for key, level in content.REORDER_THRESHOLDS.items():
            product = self.products.get(key)
            if product is not None and product.reorder_threshold is None:
                Product.objects.filter(pk=product.pk).update(reorder_threshold=level)
        for row in content.COUPONS:
            code, funding, ckey, kind, value, cap, minimum, started, days, uses = row
            starts = self.s.now - timedelta(days=started)
            self.registry.ensure(
                f"coupon:{code}",
                lambda: Coupon.objects.create(
                    code=code,
                    funded_by=funding,
                    company=self._company(ckey) if ckey else None,
                    kind=kind,
                    value=Decimal(value),
                    max_discount=Decimal(cap) if cap else None,
                    min_subtotal=Decimal(minimum),
                    starts_at=starts,
                    ends_at=starts + timedelta(days=days),
                    max_redemptions=uses,
                ),
            )
        for pkey, percent, days in content.PRODUCT_OFFERS:
            product = self.products[pkey]
            self.registry.ensure(
                f"product-offer:{pkey}",
                lambda: ProductOffer.objects.create(
                    company=product.company,
                    product=product,
                    percent=Decimal(percent),
                    starts_at=self.s.now - timedelta(days=1),
                    ends_at=self.s.now + timedelta(days=days),
                ),
            )

    def _product_images(self) -> None:
        """Every demo product gets a picture (local demo illustrations on the demo web origin).
        A picture someone already set is never replaced."""
        origin = settings.RACHEETA["FRONTEND_URL"]
        demo_pks = DemoRecord.objects.filter(model_label="marketplace.Product").values_list(
            "object_pk", flat=True
        )
        for product in Product.objects.filter(pk__in=list(demo_pks), image_url="").select_related(
            "category"
        ):
            name = content.product_image_name(product.title, product.category.slug)
            Product.objects.filter(pk=product.pk).update(
                image_url=f"{origin}/demo/products/{name}.svg"
            )

    def _campaigns(self) -> None:
        rate, _ = self.registry.ensure(
            "rate:local-demo",
            lambda: AdvertisingRate.objects.create(
                code="local-demo",
                name_ar="سعر توضيحي",
                name_en="Demo rate",
                price_per_day=Decimal("5000.00"),
                currency="IQD",
                is_active=not AdvertisingRate.objects.filter(is_active=True).exists(),
            ),
        )
        today = self.s.now.date()
        for row in content.CAMPAIGNS:
            key, ckey, pkey, status, pay_status, offset, length, ptypes, specs = row
            company, product = self._company(ckey), self.products[pkey]
            starts = today + timedelta(days=offset)
            ends = starts + timedelta(days=length - 1)
            amount = rate.price_per_day * length

            def make():
                campaign = AdvertisingCampaign.objects.create(
                    company=company,
                    product=product,
                    name=f"Demo campaign: {key}",
                    starts_on=starts,
                    ends_on=ends,
                    status=status,
                    quoted_days=length,
                    quoted_daily_rate=rate.price_per_day,
                    quoted_amount=amount,
                    quoted_currency="IQD",
                    quoted_at=self.s.now,
                    rate=rate,
                )
                verified = pay_status == "VERIFIED"
                CampaignPayment.objects.create(
                    campaign=campaign,
                    amount=amount,
                    currency="IQD",
                    status=pay_status,
                    method="BANK_TRANSFER" if verified else "",
                    reference="DEMO-NOT-A-REAL-PAYMENT" if verified else "",
                    verified_at=self.s.now if verified else None,
                    verified_by=self.admin if verified else None,
                    admin_note="Demo record only: no money was received or charged.",
                )
                for ptype in ptypes:
                    CampaignProviderType.objects.create(campaign=campaign, provider_type=ptype)
                for slug in specs:
                    CampaignSpecialty.objects.create(
                        campaign=campaign, specialty=self.s._spec[slug]
                    )
                return campaign

            campaign, created = self.registry.ensure(f"campaign:local:{key}", make)
            if created and status == "ACTIVE":
                # The product's own bounded, consent-gated outreach (current eligibility only).
                notify_campaign_audience(campaign.pk)

    # -- marketplace lifecycle helpers ---------------------------------------------------------
    def _finance_actor(self) -> Account | None:
        return self.finance or self._get("account:local-finance")

    def _run_steps(self, order: Order, buyer: Account, steps) -> None:
        """Drive one order through the REAL services (same rules, ledger and stock as the API)."""
        seller = order.merchant.account
        company = order.merchant_id
        fin = self._finance_actor()
        for step in steps:
            name, _, arg = step.partition(":")
            if name in ("pay", "complete", "refund-cancelled", "return") and fin is None:
                self.s.warnings.append(f"finance step {step} skipped: run with --with-admin")
                return
            if name == "accept":
                lifecycle.seller_transition(
                    order.pk, company_id=company, actor=seller, to_status="CONFIRMED"
                )
            elif name == "decline":
                lifecycle.seller_transition(
                    order.pk,
                    company_id=company,
                    actor=seller,
                    to_status="CANCELLED",
                    reason="نفد المخزون (توضيحي)",
                )
            elif name == "ship":
                lifecycle.seller_transition(
                    order.pk,
                    company_id=company,
                    actor=seller,
                    to_status="SHIPPED",
                    shipping_reference=f"DEMO-COURIER-{order.number[-6:]}",
                )
            elif name == "deliver":
                lifecycle.confirm_delivery(order.pk, actor=buyer)
            elif name == "pay":
                lifecycle.verify_payment(
                    order.pk, actor=fin, reference=f"SIMULATED-{order.number[-6:]}"
                )
            elif name == "complete":
                lifecycle.complete(order.pk, actor=fin)
            elif name == "buyer-cancel":
                lifecycle.buyer_cancel(order.pk, buyer=buyer, reason="غيّرت رأيي (توضيحي)")
            elif name == "refund-cancelled":
                lifecycle.refund_cancelled(order.pk, actor=fin)
            elif name in ("return", "return-request"):
                item = order.items.order_by("created_at").first()
                request = lifecycle.request_return(
                    order.pk,
                    buyer=buyer,
                    lines=[{"item": item.pk, "quantity": int(arg)}],
                    reason="المقاس غير مناسب (توضيحي) | Wrong size (demo)",
                )
                if name == "return":
                    lifecycle.decide_return(
                        request.pk,
                        company_id=company,
                        actor=seller,
                        approve=True,
                        note="مقبول (توضيحي)",
                    )
                    lifecycle.receive_return(request.pk, company_id=company, actor=seller)
                    lifecycle.refund_return(request.pk, actor=fin)
            elif name == "dispute":
                lifecycle.open_dispute(
                    order.pk, buyer=buyer, reason="وصل الجهاز لا يعمل (توضيحي) | Device not working"
                )
            else:
                raise ValueError(f"unknown demo step {step}")

    def _settlements(self) -> None:
        fin = self._finance_actor()
        if fin is None:
            return
        for ckey, outcome in content.SETTLEMENTS:
            company = self._company(ckey)

            def make():
                batch = settlement.prepare(company.pk, actor=fin)
                if outcome == "paid":
                    batch = settlement.confirm(
                        batch.pk, actor=fin, reference_note="SIMULATED-PAYOUT (no real money)"
                    )
                return SettlementBatch.objects.get(pk=batch.pk)

            if settlement.payable(company.pk) > 0 or self._get(f"settlement:{ckey}"):
                self.registry.ensure(f"settlement:{ckey}", make)

    # -- phase 3: orders, quotes, promotions --------------------------------------------------
    def phase_activity(self) -> None:
        self._guard()
        governorate, city = self.s._place("baghdad", "baghdad")
        delivery = {
            "governorate": governorate,
            "city": city,
            "address": "عنوان توضيحي | Demo address, Karrada",
            "phone": "07700000000",
            "note": "طلب توضيحي | Demo order",
        }
        for tag, buyer_key, lines, codes, method, steps in content.MARKET_SCENARIOS:
            buyer = self.s.accounts.get(buyer_key) or self._get(f"account:{buyer_key}")

            def make():
                result, _ = store_checkout.place(
                    buyer,
                    items=[{"product": self.products[k].pk, "quantity": q} for k, q in lines],
                    coupons=codes,
                    delivery=delivery,
                    payment_method=method,
                    idempotency_key=f"demo-{tag}",
                )
                for order in result.orders.order_by("created_at"):
                    self._run_steps(order, buyer, steps)
                return Checkout.objects.get(pk=result.pk)

            self.registry.ensure(f"checkout:{tag}", make)
        quotes: dict[str, QuoteRequest] = {}
        for tag, provider_key, pkey, qty, outcome, price in content.QUOTES:
            provider = self._provider(provider_key)
            product = self.products[pkey]

            def make():
                quote = commerce.request_quote(
                    provider,
                    account=provider.account,
                    product_id=product.pk,
                    quantity=qty,
                    message="طلب توضيحي | Demo request",
                )
                if outcome in ("QUOTED", "ACCEPTED"):
                    commerce.respond_quote(
                        quote.pk,
                        company_id=quote.company_id,
                        actor=quote.company.account,
                        unit_price=Decimal(price),
                        note="سعر توضيحي | Demo price",
                    )
                if outcome == "ACCEPTED":
                    commerce.close_as_requester(
                        quote.pk, provider=provider, actor=provider.account, outcome="ACCEPTED"
                    )
                return QuoteRequest.objects.get(pk=quote.pk)

            quotes[tag], _ = self.registry.ensure(f"quote:{tag}", make)
        for tag, provider_key, steps in content.QUOTE_ORDERS:
            provider = self._provider(provider_key)
            quote = quotes.get(tag)

            def make():
                result, _ = commerce.order_from_quote(
                    quote.pk,
                    provider=provider,
                    account=provider.account,
                    delivery=delivery,
                    payment_method="MANUAL_TRANSFER",
                    idempotency_key=f"demo-quote-{tag}",
                )
                self._run_steps(result.orders.get(), provider.account, steps)
                return Checkout.objects.get(pk=result.pk)

            if quote is not None and quote.status in ("ACCEPTED", "ORDERED"):
                self.registry.ensure(f"checkout:quote:{tag}", make)
        self._settlements()
        admin = self.admin or self._get("account:local-admin")
        for tag, listing_index, types, days, outcome in content.PROMOTIONS:
            listing = self._get(f"listing:{listing_index}")
            if listing is None:
                self.s.warnings.append(f"promotion listing missing: {listing_index}")
                continue

            def make():
                promotion = promotions.request_promotion(
                    listing.seller, listing.pk, target_provider_types=types, days=days
                )
                if outcome == "ACTIVE":
                    promotions.approve_promotion(promotion.pk, decided_by=admin)
                elif outcome == "REJECTED":
                    promotions.reject_promotion(
                        promotion.pk,
                        decided_by=admin,
                        reason="صور ناقصة (توضيحي) | Missing photos (demo)",
                    )
                return ListingPromotion.objects.get(pk=promotion.pk)

            self.registry.ensure(f"promotion:{tag}", make)
        self._product_images()  # after the commerce step committed its product records
        self._account_types()
