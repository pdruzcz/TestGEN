"""Unit tests for LogicStructuresCodeProvider (Story 3.4 closure)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.analysis.uml.code_structure_provider import (
    LogicStructuresCodeProvider,
    fetch_logic_structures,
)


def _payload() -> dict:
    """logic_structures payload shape (mirrors CodeStructureCatalog.to_dict)."""
    return {
        "classes": [
            {
                "name": "UserService",
                "is_interface": False,
                "attributes": [
                    {"name": "email", "type": "str", "visibility": "private"},
                    {"name": "counter", "type": "int"},
                ],
                "methods": [
                    {
                        "name": "create",
                        "return_type": "User",
                        "parameters": [
                            {"name": "data"},
                            {"name": "strict", "type": "bool"},
                        ],
                    },
                    {"name": "delete", "parameters": []},
                    {"name": "", "parameters": []},  # anonymous → skipped
                ],
            },
            {
                # interface → exposed via get_interfaces
                "name": "Runnable",
                "is_interface": True,
                "methods": [{"name": "run", "parameters": []}],
            },
            {
                "name": "",  # anonymous class → skipped
                "is_interface": False,
            },
        ],
        "functions": [],
        "modules": [],
    }


def _db_with_first(first):
    """AsyncMock session whose ``await db.execute(...)`` yields a sync result
    whose ``.scalars().first()`` returns ``first``."""
    result = MagicMock()
    result.scalars.return_value.first.return_value = first
    db = AsyncMock()
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
async def test_load_and_get_classes_maps_payload():
    db = _db_with_first(None)
    provider = LogicStructuresCodeProvider(db)
    await provider.load(uuid4())
    # no real row → payload stays None → empty (fallback)
    assert provider.get_classes(uuid4()) == []
    assert provider.get_interfaces(uuid4()) == []


def test_get_classes_maps_attributes_and_methods():
    provider = LogicStructuresCodeProvider(db=AsyncMock())
    provider._payload = _payload()

    classes = provider.get_classes(uuid4())
    assert [c.name for c in classes] == ["UserService"]

    svc = classes[0]
    assert [a.name for a in svc.attributes] == ["email", "counter"]
    assert svc.attributes[0].type == "str"
    assert svc.attributes[0].visibility == "private"

    assert [m.name for m in svc.methods] == ["create", "delete"]
    create = svc.methods[0]
    assert create.return_type == "User"
    assert create.parameter_count == 2  # len(parameters)
    assert svc.methods[1].parameter_count == 0


def test_get_interfaces_maps_is_interface_classes():
    provider = LogicStructuresCodeProvider(db=AsyncMock())
    provider._payload = _payload()

    interfaces = provider.get_interfaces(uuid4())
    assert [i.name for i in interfaces] == ["Runnable"]
    assert [m.name for m in interfaces[0].methods] == ["run"]


def test_empty_payload_returns_empty_lists():
    provider = LogicStructuresCodeProvider(db=AsyncMock())
    provider._payload = None
    assert provider.get_classes(uuid4()) == []
    assert provider.get_interfaces(uuid4()) == []

    provider._payload = {"classes": []}
    assert provider.get_classes(uuid4()) == []
    assert provider.get_interfaces(uuid4()) == []


@pytest.mark.asyncio
async def test_fetch_logic_structures_returns_result_data_when_found():
    ar = MagicMock()
    ar.result_data = {"classes": [{"name": "X"}]}

    db = _db_with_first(ar)
    payload = await fetch_logic_structures(db, uuid4())
    assert payload == {"classes": [{"name": "X"}]}


@pytest.mark.asyncio
async def test_fetch_logic_structures_returns_none_when_absent():
    db = _db_with_first(None)
    assert await fetch_logic_structures(db, uuid4()) is None
