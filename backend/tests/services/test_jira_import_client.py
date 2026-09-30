"""Klient importu z Jiry — migracja search na v3 ``/search/jql`` (2026-09-28).

Legacy ``GET /rest/api/2/search`` został usunięty przez Atlassian (410).
Testy trzymają klienta na nowym endpoincie, paginacji ``nextPageToken``
i konwersji opisów ADF na znaczniki wiki, które czyta parser kryteriów.
"""

import base64
import json

import httpx
import pytest

from app.services.integrations.jira_service import (
    JiraImportClient,
    JiraImportError,
    adf_to_wiki,
    parse_issue,
)

_ADF_DESCRIPTION = {
    "type": "doc",
    "content": [
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Kryteria akceptacji"}],
        },
        {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Kryterium 1"}],
                        }
                    ],
                }
            ],
        },
    ],
}


def _issue_raw(key: str) -> dict:
    return {
        "key": key,
        "fields": {
            "summary": "Historyjka",
            "description": _ADF_DESCRIPTION,
            "issuetype": {"name": "Story"},
            "status": {"name": "To Do"},
            "labels": [],
        },
    }


def _install_transport(monkeypatch, handler) -> list[httpx.Request]:
    """Klient tworzy własny AsyncClient — podstawiamy transport i zbieramy requesty."""
    seen: list[httpx.Request] = []
    real_client = httpx.AsyncClient

    def wrapped_handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    transport = httpx.MockTransport(wrapped_handler)

    def factory(**kwargs):
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr("app.services.integrations.jira_service.httpx.AsyncClient", factory)
    return seen


@pytest.mark.asyncio
async def test_search_idzie_na_v3_search_jql_z_paginacja(monkeypatch):
    pages = [
        {"issues": [_issue_raw("QA-1")], "nextPageToken": "token-2"},
        {"issues": [_issue_raw("QA-2")]},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        page = pages[0] if "nextPageToken" not in body else pages[1]
        return httpx.Response(200, json=page)

    seen = _install_transport(monkeypatch, handler)
    client = JiraImportClient("https://firma.atlassian.net", "qa@firma.pl", "tok")

    issues = await client.search_issues("project=QA")

    assert [issue.key for issue in issues] == ["QA-1", "QA-2"]
    assert len(seen) == 2
    assert all(r.method == "POST" for r in seen)
    assert all(r.url.path == "/rest/api/3/search/jql" for r in seen)
    assert json.loads(seen[1].content)["nextPageToken"] == "token-2"
    expected_auth = "Basic " + base64.b64encode(b"qa@firma.pl:tok").decode()
    assert seen[0].headers["authorization"] == expected_auth
    # Opis w ADF sprowadzony na wiki — tego formatu szuka parser kryteriów.
    assert "h2. Kryteria akceptacji" in issues[0].description
    assert "* Kryterium 1" in issues[0].description


@pytest.mark.asyncio
async def test_search_410_ma_czytelny_komunikat(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(410)

    _install_transport(monkeypatch, handler)
    client = JiraImportClient("https://firma.atlassian.net", "qa@firma.pl", "tok")

    with pytest.raises(JiraImportError, match="usunął ten endpoint"):
        await client.search_issues("project=QA")


def test_parse_issue_opis_adf_przechodzi_na_wiki():
    issue = parse_issue(_issue_raw("QA-1"))
    assert issue.description == "h2. Kryteria akceptacji\n* Kryterium 1"


def test_adf_to_wiki_naglowek_akapit_i_listy_zagniezdzone():
    adf = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Kontekst."}]},
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "Acceptance Criteria"}],
            },
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Pierwsze"}],
                            },
                            {
                                "type": "bulletList",
                                "content": [
                                    {
                                        "type": "listItem",
                                        "content": [
                                            {
                                                "type": "paragraph",
                                                "content": [{"type": "text", "text": "Zagnieżdżone"}],
                                            }
                                        ],
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Drugie"}],
                            }
                        ],
                    },
                ],
            },
        ],
    }

    assert adf_to_wiki(adf) == "\n".join(
        [
            "Kontekst.",
            "h3. Acceptance Criteria",
            "* Pierwsze",
            "** Zagnieżdżone",
            "* Drugie",
        ]
    )
