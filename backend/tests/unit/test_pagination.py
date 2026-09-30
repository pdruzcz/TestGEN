from unittest.mock import MagicMock

from app.core.pagination import PaginationParams, set_pagination_headers


def test_pagination_params_with_explicit_values():
    params = PaginationParams(page=1, page_size=20)
    assert params.page == 1
    assert params.page_size == 20


def test_pagination_params_offset():
    params = PaginationParams(page=3, page_size=10)
    assert params.offset == 20


def test_pagination_params_limit():
    params = PaginationParams(page=1, page_size=50)
    assert params.limit == 50


def test_pagination_params_first_page_offset():
    params = PaginationParams(page=1, page_size=20)
    assert params.offset == 0


def test_set_pagination_headers_total_count():
    response = MagicMock()
    response.headers = {}
    params = PaginationParams(page=1, page_size=10)

    set_pagination_headers(response, total=100, params=params, base_url="/api/v1/items")

    assert response.headers["X-Total-Count"] == "100"


def test_set_pagination_headers_link_next():
    response = MagicMock()
    response.headers = {}
    params = PaginationParams(page=1, page_size=10)

    set_pagination_headers(response, total=100, params=params, base_url="/api/v1/items")

    assert 'rel="next"' in response.headers["Link"]
    assert "page=2" in response.headers["Link"]


def test_set_pagination_headers_link_no_next_on_last():
    response = MagicMock()
    response.headers = {}
    params = PaginationParams(page=10, page_size=10)

    set_pagination_headers(response, total=100, params=params, base_url="/api/v1/items")

    assert 'rel="next"' not in response.headers["Link"]


def test_set_pagination_headers_link_prev():
    response = MagicMock()
    response.headers = {}
    params = PaginationParams(page=3, page_size=10)

    set_pagination_headers(response, total=100, params=params, base_url="/api/v1/items")

    assert 'rel="prev"' in response.headers["Link"]
    assert "page=2" in response.headers["Link"]


def test_set_pagination_headers_link_no_prev_on_first():
    response = MagicMock()
    response.headers = {}
    params = PaginationParams(page=1, page_size=10)

    set_pagination_headers(response, total=100, params=params, base_url="/api/v1/items")

    assert 'rel="prev"' not in response.headers["Link"]


def test_set_pagination_headers_first_and_last_always_present():
    response = MagicMock()
    response.headers = {}
    params = PaginationParams(page=5, page_size=10)

    set_pagination_headers(response, total=100, params=params, base_url="/api/v1/items")

    assert 'rel="first"' in response.headers["Link"]
    assert 'rel="last"' in response.headers["Link"]
