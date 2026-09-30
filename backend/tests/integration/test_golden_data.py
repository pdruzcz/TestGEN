"""Tests for golden test data management - Story 1.45"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.services.golden_data import (
    GoldenDataManager,
    GoldenDataSet,
    GoldenDataType,
    get_golden_data_manager,
)


class TestGoldenDataType:
    """Test GoldenDataType enum (Story 1.45)."""

    def test_data_type_values(self):
        """Test all data type values exist."""
        assert GoldenDataType.EXPECTED_OUTPUT == "expected_output"
        assert GoldenDataType.MOCK_DATA == "mock_data"
        assert GoldenDataType.FIXTURE_DATA == "fixture_data"
        assert GoldenDataType.API_RESPONSE == "api_response"
        assert GoldenDataType.UI_SNAPSHOT == "ui_snapshot"
        assert GoldenDataType.PERFORMANCE_BASELINE == "performance_baseline"


class TestGoldenDataSet:
    """Test GoldenDataSet dataclass (Story 1.45)."""

    def test_dataset_creation(self):
        """Test creating a golden data set."""
        dataset = GoldenDataSet(
            name="test_data",
            data_type=GoldenDataType.EXPECTED_OUTPUT,
            version="1.0",
            data={"key": "value"},
            tags=["unit", "api"],
        )
        assert dataset.name == "test_data"
        assert dataset.data_type == GoldenDataType.EXPECTED_OUTPUT
        assert dataset.data == {"key": "value"}


class TestGoldenDataManager:
    """Test GoldenDataManager (Story 1.45)."""

    def test_manager_initialization(self):
        """Test manager can be initialized."""
        manager = GoldenDataManager()
        assert manager is not None
        assert manager.storage_path.exists()

    def test_get_golden_data_manager(self):
        """Test getting manager singleton."""
        manager = get_golden_data_manager()
        assert isinstance(manager, GoldenDataManager)

    def test_save_and_load_golden_data(self, tmp_path):
        """Test saving and loading golden data."""
        manager = GoldenDataManager(str(tmp_path))

        dataset = GoldenDataSet(
            name="test_api_response",
            data_type=GoldenDataType.API_RESPONSE,
            version="1.0",
            data={"status": "success", "data": {"id": 123}},
            tags=["api", "integration"],
        )

        file_path = manager.save_golden_data(dataset)
        assert Path(file_path).exists()

        loaded = manager.load_golden_data("test_api_response", "1.0")
        assert loaded is not None
        assert loaded.name == "test_api_response"
        assert loaded.data == {"status": "success", "data": {"id": 123}}

    def test_load_nonexistent_data(self, tmp_path):
        """Test loading non-existent golden data."""
        manager = GoldenDataManager(str(tmp_path))
        loaded = manager.load_golden_data("nonexistent", "1.0")
        assert loaded is None

    def test_compare_with_golden_pass(self, tmp_path):
        """Test comparison with matching golden data."""
        manager = GoldenDataManager(str(tmp_path))

        dataset = GoldenDataSet(
            name="expected_result",
            data_type=GoldenDataType.EXPECTED_OUTPUT,
            version="1.0",
            data={"result": 42, "message": "success"},
        )
        manager.save_golden_data(dataset)

        actual = {"result": 42, "message": "success"}
        result = manager.compare_with_golden(actual, "expected_result", "1.0")

        assert result["status"] == "pass"
        assert result["matches"] is True
        assert len(result["differences"]) == 0

    def test_compare_with_golden_fail(self, tmp_path):
        """Test comparison with non-matching golden data."""
        manager = GoldenDataManager(str(tmp_path))

        dataset = GoldenDataSet(
            name="expected_result",
            data_type=GoldenDataType.EXPECTED_OUTPUT,
            version="1.0",
            data={"result": 42, "message": "success"},
        )
        manager.save_golden_data(dataset)

        actual = {"result": 99, "message": "success"}
        result = manager.compare_with_golden(actual, "expected_result", "1.0")

        assert result["status"] == "fail"
        assert result["matches"] is False
        assert len(result["differences"]) > 0

    def test_compare_missing_field(self, tmp_path):
        """Test comparison with missing field."""
        manager = GoldenDataManager(str(tmp_path))

        dataset = GoldenDataSet(
            name="full_data",
            data_type=GoldenDataType.EXPECTED_OUTPUT,
            version="1.0",
            data={"a": 1, "b": 2, "c": 3},
        )
        manager.save_golden_data(dataset)

        actual = {"a": 1, "b": 2}
        result = manager.compare_with_golden(actual, "full_data", "1.0")

        assert result["status"] == "fail"
        assert any(d["type"] == "missing" for d in result["differences"])

    def test_compare_extra_field(self, tmp_path):
        """Test comparison with extra field."""
        manager = GoldenDataManager(str(tmp_path))

        dataset = GoldenDataSet(
            name="minimal_data",
            data_type=GoldenDataType.EXPECTED_OUTPUT,
            version="1.0",
            data={"a": 1, "b": 2},
        )
        manager.save_golden_data(dataset)

        actual = {"a": 1, "b": 2, "c": 3}
        result = manager.compare_with_golden(actual, "minimal_data", "1.0")

        assert result["status"] == "fail"
        assert any(d["type"] == "extra" for d in result["differences"])

    def test_update_golden_data(self, tmp_path):
        """Test updating golden data with new version."""
        manager = GoldenDataManager(str(tmp_path))

        # Create initial version
        dataset = GoldenDataSet(
            name="api_response",
            data_type=GoldenDataType.API_RESPONSE,
            version="1.0",
            data={"version": 1},
        )
        manager.save_golden_data(dataset)

        # Update to new version
        updated = manager.update_golden_data("api_response", {"version": 2})
        assert updated.version == "1.1"
        assert updated.data == {"version": 2}

        # Load both versions
        v1 = manager.load_golden_data("api_response", "1.0")
        v2 = manager.load_golden_data("api_response", "1.1")

        assert v1.data["version"] == 1
        assert v2.data["version"] == 2

    def test_list_golden_data(self, tmp_path):
        """Test listing all golden data."""
        manager = GoldenDataManager(str(tmp_path))

        datasets = [
            GoldenDataSet(
                name="test1",
                data_type=GoldenDataType.EXPECTED_OUTPUT,
                version="1.0",
                data={"test": 1},
            ),
            GoldenDataSet(
                name="test2",
                data_type=GoldenDataType.MOCK_DATA,
                version="1.0",
                data={"test": 2},
            ),
        ]

        for ds in datasets:
            manager.save_golden_data(ds)

        all_data = manager.list_golden_data()
        assert len(all_data) == 2

        api_data = manager.list_golden_data(GoldenDataType.EXPECTED_OUTPUT)
        assert len(api_data) == 1
        assert api_data[0].name == "test1"

    def test_deep_compare(self, tmp_path):
        """Test deep comparison of nested structures."""
        manager = GoldenDataManager(str(tmp_path))

        # Test nested dict comparison
        assert manager._deep_compare({"a": {"b": 1}}, {"a": {"b": 1}}) is True
        assert manager._deep_compare({"a": {"b": 1}}, {"a": {"b": 2}}) is False

        # Test list comparison
        assert manager._deep_compare([1, 2, 3], [1, 2, 3]) is True
        assert manager._deep_compare([1, 2, 3], [1, 2, 4]) is False

        # Test type mismatch
        assert manager._deep_compare(123, "123") is False

    def test_find_differences(self, tmp_path):
        """Test finding differences between structures."""
        manager = GoldenDataManager(str(tmp_path))

        expected = {"a": 1, "b": 2}
        actual = {"a": 1, "b": 3}

        diffs = manager._find_differences(actual, expected)
        assert len(diffs) == 1
        assert diffs[0]["path"] == "b"
        assert diffs[0]["type"] == "mismatch"


@pytest.mark.integration
class TestGoldenDataIntegration:
    """Integration tests for golden data manager (Story 1.45)."""

    def test_full_golden_data_workflow(self, tmp_path):
        """Test complete golden data workflow."""
        manager = GoldenDataManager(str(tmp_path))

        # Create golden data from test result
        test_result = {
            "user": {"id": 123, "name": "Test User"},
            "status": "active",
        }

        dataset = GoldenDataSet(
            name="user_creation_test",
            data_type=GoldenDataType.EXPECTED_OUTPUT,
            version="1.0",
            data=test_result,
            tags=["api", "user"],
        )
        manager.save_golden_data(dataset)

        # Compare with matching result
        new_result = {
            "user": {"id": 123, "name": "Test User"},
            "status": "active",
        }

        comparison = manager.compare_with_golden(new_result, "user_creation_test", "1.0")
        assert comparison["status"] == "pass"

        # Update golden data for new version
        updated_result = {
            "user": {"id": 123, "name": "Test User", "email": "test@example.com"},
            "status": "active",
        }

        manager.update_golden_data("user_creation_test", updated_result)

        # Old version should still exist
        old_version = manager.load_golden_data("user_creation_test", "1.0")
        assert "email" not in old_version.data["user"]

        # New version should have email
        new_version = manager.load_golden_data("user_creation_test", "1.1")
        assert new_version.data["user"]["email"] == "test@example.com"
