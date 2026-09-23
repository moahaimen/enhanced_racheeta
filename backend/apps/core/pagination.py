from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Consistent pagination for every list endpoint.

    Response shape: {"count", "next", "previous", "results"}.
    Clients may request `?page=N&page_size=M` with M capped at 100.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
