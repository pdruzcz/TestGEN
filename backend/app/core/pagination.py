from dataclasses import dataclass

from fastapi import Query, Response


@dataclass
class PaginationParams:
    page: int = Query(default=1, ge=1, description="Page number")
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def set_pagination_headers(response: Response, total: int, params: PaginationParams, base_url: str) -> None:
    response.headers["X-Total-Count"] = str(total)

    total_pages = max(1, (total + params.page_size - 1) // params.page_size)
    links: list[str] = []

    if params.page < total_pages:
        links.append(f'<{base_url}?page={params.page + 1}&page_size={params.page_size}>; rel="next"')
    if params.page > 1:
        links.append(f'<{base_url}?page={params.page - 1}&page_size={params.page_size}>; rel="prev"')
    links.append(f'<{base_url}?page=1&page_size={params.page_size}>; rel="first"')
    links.append(f'<{base_url}?page={total_pages}&page_size={params.page_size}>; rel="last"')

    response.headers["Link"] = ", ".join(links)
