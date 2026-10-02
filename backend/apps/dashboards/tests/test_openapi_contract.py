"""The published contract: read-only, parameterless, authenticated, and free of private fields."""

from pathlib import Path

import yaml
from drf_spectacular.generators import SchemaGenerator

COMMITTED = yaml.safe_load(
    Path(__file__).resolve().parents[4].joinpath("docs/api/openapi.yaml").read_text()
)
PATHS = {
    "/api/v1/dashboards/": "DashboardIndex",
    "/api/v1/dashboards/patient": "PatientDashboard",
    "/api/v1/dashboards/doctor": "DoctorDashboard",
    "/api/v1/dashboards/facility": "FacilityDashboard",
    "/api/v1/dashboards/company": "MedicalCompanyDashboard",
    "/api/v1/dashboards/recruiter": "RecruiterDashboard",
    "/api/v1/dashboards/admin": "AdminDashboard",
}
FORBIDDEN_PROPERTIES = {
    "patient_note",
    "email",
    "phone",
    "phone_number",
    "public_email",
    "token",
    "password",
    "cover_text",
    "snapshot",
    "note",
    "impressions",
    "clicks",
    "conversions",
    "revenue",
}


def _all_property_names(schema, name, seen=None):
    seen = seen if seen is not None else set()
    if name in seen:
        return set()
    seen.add(name)
    names = set()
    node = schema["components"]["schemas"][name]
    for prop, value in node.get("properties", {}).items():
        names.add(prop)
        refs = [value.get("$ref")] + [part.get("$ref") for part in value.get("allOf", [])]
        items = value.get("items", {})
        refs.append(items.get("$ref"))
        for ref in filter(None, refs):
            names |= _all_property_names(schema, ref.rsplit("/", 1)[-1], seen)
    return names


def _check(schema):
    for path, component in PATHS.items():
        operations = schema["paths"][path]
        assert set(operations) == {"get"}, path  # read-only
        get = operations["get"]
        assert not get.get("parameters"), path  # no client input at all
        assert get["security"], path  # authenticated
        ref = get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith(f"/{component}"), path
        assert not (_all_property_names(schema, component) & FORBIDDEN_PROPERTIES), component


def test_committed_openapi_documents_every_dashboard():
    _check(COMMITTED)


def test_generated_openapi_documents_every_dashboard():
    _check(SchemaGenerator().get_schema(request=None, public=True))


def test_the_existing_company_dashboard_contract_is_not_shadowed():
    # A component-name collision once replaced this schema silently; pin the existing shape.
    existing = COMMITTED["components"]["schemas"]["CompanyDashboard"]["properties"]
    assert {"products_total", "products_active", "products_exposable"} <= set(existing)
