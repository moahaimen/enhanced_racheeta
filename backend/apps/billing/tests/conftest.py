import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.billing import services
from apps.billing.models import Plan
from apps.billing.types import Audience, SubjectType


@pytest.fixture
def employer_billing(db):
    return services.get_or_create_billing_account(
        SubjectType.ORGANIZATION, uuid.uuid4(), Audience.EMPLOYER
    )


@pytest.fixture
def seeker_billing(db):
    return services.get_or_create_billing_account(
        SubjectType.ACCOUNT, uuid.uuid4(), Audience.JOB_SEEKER
    )


@pytest.fixture
def admin(db):
    return Account.objects.create_superuser(
        email="admin@example.com", password="Str0ng-Passw0rd!", full_name="Admin"
    )


@pytest.fixture
def admin_client(admin):
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


@pytest.fixture
def plan(db):
    return Plan.objects.get(code="BASIC")


@pytest.fixture
def active_basic(employer_billing, plan, admin, account_factory):
    sub = services.request_subscription(employer_billing, plan, requested_by=account_factory())
    return services.activate_subscription(sub, admin=admin, reference="TRX-1")
