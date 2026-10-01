"""The notification list publishes the pagination parameters it really supports."""

from pathlib import Path

import yaml
from drf_spectacular.generators import SchemaGenerator

from apps.core.pagination import StandardPagination

COMMITTED = yaml.safe_load(
    Path(__file__).resolve().parents[4].joinpath("docs/api/openapi.yaml").read_text()
)
PATH = "/api/v1/notifications/"


def _query_params(schema):
    operation = schema["paths"][PATH]["get"]
    return {p["name"]: p for p in operation.get("parameters", []) if p["in"] == "query"}


def _assert_pagination_contract(schema):
    params = _query_params(schema)
    assert {"page", "page_size"} <= set(params)
    for name in ("page", "page_size"):
        assert params[name]["schema"]["type"] == "integer"
        assert not params[name].get("required", False)
    assert str(StandardPagination.max_page_size) in params["page_size"]["description"]
    assert str(StandardPagination.page_size) in params["page_size"]["description"]
    # The response shape is unchanged.
    ok = schema["paths"][PATH]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert ok["$ref"].endswith("/PaginatedNotification")
    paginated = schema["components"]["schemas"]["PaginatedNotification"]
    assert set(paginated["properties"]) == {"count", "next", "previous", "results"}


def test_committed_openapi_documents_page_and_page_size():
    _assert_pagination_contract(COMMITTED)


def test_generated_openapi_documents_page_and_page_size():
    generated = SchemaGenerator().get_schema(request=None, public=True)
    _assert_pagination_contract(generated)


def test_only_the_list_operation_takes_pagination_parameters():
    for path, operations in COMMITTED["paths"].items():
        if not path.startswith("/api/v1/notifications/") or path == PATH:
            continue
        for operation in operations.values():
            names = {p["name"] for p in operation.get("parameters", [])}
            assert not names & {"page", "page_size"}
