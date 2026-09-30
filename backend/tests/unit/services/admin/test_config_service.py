"""Testy config_service — Story 6.15, Task 10 (AC7)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.models.platform_setting import PlatformSetting
from app.services.admin import config_service
from tests.factories import make_user


@pytest.fixture()
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


def _rows(rows: list) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


class TestGetConfig:
    async def test_zwraca_wartosci_domyslne_gdy_brak_wpisow(self, mock_db):
        mock_db.execute.return_value = _rows([])

        config = await config_service.get_config(mock_db)

        assert set(config) == set(config_service.CONFIG_SECTIONS)
        assert config["maintenance"]["enabled"] is False
        assert config["limits"]["max_file_size_mb"] > 0
        assert isinstance(config["feature_flags"], dict)

    async def test_nadpisuje_domyslne_wartosciami_z_bazy(self, mock_db):
        mock_db.execute.return_value = _rows(
            [PlatformSetting(key="maintenance", value={"enabled": True, "message": "Przerwa"})]
        )

        config = await config_service.get_config(mock_db)

        assert config["maintenance"] == {"enabled": True, "message": "Przerwa"}
        # pozostałe sekcje nadal domyślne
        assert config["llm"]["provider"] in {"openai", "anthropic"}

    async def test_scala_czesciowa_sekcje_z_domyslnymi(self, mock_db):
        mock_db.execute.return_value = _rows([PlatformSetting(key="llm", value={"temperature": 0.9})])

        config = await config_service.get_config(mock_db)

        assert config["llm"]["temperature"] == 0.9
        assert "model" in config["llm"]

    async def test_ignoruje_nieznane_klucze_z_bazy(self, mock_db):
        mock_db.execute.return_value = _rows([PlatformSetting(key="cos_starego", value={"x": 1})])

        config = await config_service.get_config(mock_db)

        assert "cos_starego" not in config


class TestUpdateConfig:
    async def test_zapisuje_nowa_sekcje(self, mock_db):
        mock_db.execute.return_value = _rows([])
        admin = make_user(is_admin=True)

        config = await config_service.update_config(
            mock_db,
            admin=admin,
            sections={"maintenance": {"enabled": True, "message": "Serwis"}},
        )

        assert config["maintenance"]["enabled"] is True
        mock_db.add.assert_called()

    async def test_aktualizuje_istniejacy_wpis_zamiast_dodawac(self, mock_db):
        existing = PlatformSetting(key="maintenance", value={"enabled": False, "message": ""})
        mock_db.execute.return_value = _rows([existing])
        admin = make_user(is_admin=True)

        await config_service.update_config(
            mock_db,
            admin=admin,
            sections={"maintenance": {"enabled": True}},
        )

        assert existing.value["enabled"] is True
        assert existing.updated_by == admin.id

    async def test_scalanie_czesciowe_nie_kasuje_pozostalych_pol(self, mock_db):
        mock_db.execute.return_value = _rows([])
        admin = make_user(is_admin=True)

        config = await config_service.update_config(
            mock_db,
            admin=admin,
            sections={"limits": {"max_file_size_mb": 250}},
        )

        assert config["limits"]["max_file_size_mb"] == 250
        assert config["limits"]["max_users_per_tenant"] > 0

    async def test_odrzuca_nieznana_sekcje(self, mock_db):
        mock_db.execute.return_value = _rows([])

        with pytest.raises(ValidationError):
            await config_service.update_config(
                mock_db,
                admin=make_user(is_admin=True),
                sections={"nieznana": {"a": 1}},
            )

    async def test_odrzuca_niepoprawna_wartosc(self, mock_db):
        mock_db.execute.return_value = _rows([])

        with pytest.raises(ValidationError):
            await config_service.update_config(
                mock_db,
                admin=make_user(is_admin=True),
                sections={"limits": {"max_file_size_mb": -5}},
            )

    async def test_zapisuje_wpis_w_logu_audytu(self, mock_db):
        mock_db.execute.return_value = _rows([])
        admin = make_user(is_admin=True)

        await config_service.update_config(
            mock_db,
            admin=admin,
            sections={"maintenance": {"enabled": True}},
            ip_address="10.0.0.1",
        )

        added = [call.args[0] for call in mock_db.add.call_args_list]
        audit = [row for row in added if getattr(row, "action", None) == "platform.config_updated"]
        assert len(audit) == 1
        assert audit[0].ip_address == "10.0.0.1"
        assert audit[0].user_id == admin.id

    async def test_brak_zmian_nie_tworzy_wpisu_audytu(self, mock_db):
        current = await config_service.get_config(AsyncMock(execute=AsyncMock(return_value=_rows([]))))
        mock_db.execute.return_value = _rows([])

        await config_service.update_config(
            mock_db,
            admin=make_user(is_admin=True),
            sections={"maintenance": dict(current["maintenance"])},
        )

        added = [call.args[0] for call in mock_db.add.call_args_list]
        assert not [row for row in added if getattr(row, "action", None) == "platform.config_updated"]

    async def test_uzywa_nil_uuid_jako_tenanta(self, mock_db):
        from app.core.constants import NIL_UUID

        mock_db.execute.return_value = _rows([])

        await config_service.update_config(
            mock_db,
            admin=make_user(is_admin=True),
            sections={"maintenance": {"enabled": True}},
        )

        added = [call.args[0] for call in mock_db.add.call_args_list]
        audit = next(row for row in added if getattr(row, "action", None) == "platform.config_updated")
        assert audit.tenant_id == uuid.UUID(NIL_UUID)
