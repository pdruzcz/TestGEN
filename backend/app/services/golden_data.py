"""Golden test data management - Story 1.45

Provides golden data for test validation:
- Expected output storage and retrieval
- Test result comparison
- Golden data versioning
- Data import/export
- Snapshot management
- Change detection in golden data
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.database import get_sync_session
from app.models.test_case import TestCase

logger = logging.getLogger(__name__)


class GoldenDataType(StrEnum):
    """Types of golden test data."""
    EXPECTED_OUTPUT = "expected_output"
    MOCK_DATA = "mock_data"
    FIXTURE_DATA = "fixture_data"
    API_RESPONSE = "api_response"
    UI_SNAPSHOT = "ui_snapshot"
    PERFORMANCE_BASELINE = "performance_baseline"


@dataclass
class GoldenDataSet:
    """A collection of golden test data."""
    name: str
    data_type: GoldenDataType
    version: str
    data: dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


class GoldenDataManager:
    """Manage golden test data for test validation."""

    def __init__(self, storage_path: str | None = None):
        """Initialize golden data manager.

        Args:
            storage_path: Path to store golden data files
        """
        self.storage_path = Path(storage_path or "data/golden")
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save_golden_data(self, dataset: GoldenDataSet) -> str:
        """Save golden data to storage.

        Returns:
            Path to saved file
        """
        filename = f"{dataset.name}_{dataset.version}.json"
        file_path = self.storage_path / filename

        data_dict = {
            "name": dataset.name,
            "data_type": dataset.data_type.value,
            "version": dataset.version,
            "created_at": dataset.created_at.isoformat(),
            "metadata": dataset.metadata,
            "tags": dataset.tags,
            "data": dataset.data,
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved golden data: {filename}")
        return str(file_path)

    def load_golden_data(self, name: str, version: str | None = None) -> GoldenDataSet | None:
        """Load golden data from storage.

        Args:
            name: Name of the golden data set
            version: Optional version (uses latest if not specified)

        Returns:
            GoldenDataSet or None if not found
        """
        if version:
            filename = f"{name}_{version}.json"
        else:
            # Find latest version
            files = list(self.storage_path.glob(f"{name}_*.json"))
            if not files:
                return None
            filename = max(files, key=lambda f: f.stat().st_mtime).name

        file_path = self.storage_path / filename

        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data_dict = json.load(f)

        return GoldenDataSet(
            name=data_dict["name"],
            data_type=GoldenDataType(data_dict["data_type"]),
            version=data_dict["version"],
            data=data_dict["data"],
            created_at=datetime.fromisoformat(data_dict["created_at"]),
            metadata=data_dict.get("metadata", {}),
            tags=data_dict.get("tags", []),
        )

    def compare_with_golden(
        self, actual: Any, golden_name: str, version: str | None = None
    ) -> dict[str, Any]:
        """Compare actual results with golden data.

        Args:
            actual: Actual test result
            golden_name: Name of golden data set
            version: Optional version

        Returns:
            Comparison result with pass/fail status
        """
        golden = self.load_golden_data(golden_name, version)
        if not golden:
            return {
                "status": "error",
                "message": f"Golden data not found: {golden_name}",
            }

        golden_data = golden.data
        matches = self._deep_compare(actual, golden_data)

        return {
            "status": "pass" if matches else "fail",
            "golden_name": golden_name,
            "golden_version": golden.version,
            "matches": matches,
            "differences": self._find_differences(actual, golden_data) if not matches else [],
        }

    def _deep_compare(self, obj1: Any, obj2: Any) -> bool:
        """Deep compare two objects."""
        if type(obj1) != type(obj2):
            return False

        if isinstance(obj1, dict):
            if set(obj1.keys()) != set(obj2.keys()):
                return False
            return all(self._deep_compare(obj1[k], obj2[k]) for k in obj1.keys())

        if isinstance(obj1, (list, tuple)):
            if len(obj1) != len(obj2):
                return False
            return all(self._deep_compare(obj1[i], obj2[i]) for i in range(len(obj1)))

        return obj1 == obj2

    def _find_differences(self, actual: Any, expected: Any, path: str = "") -> list[dict[str, Any]]:
        """Find differences between actual and expected values."""
        differences = []

        if type(actual) != type(expected):
            differences.append({
                "path": path,
                "expected_type": type(expected).__name__,
                "actual_type": type(actual).__name__,
            })
            return differences

        if isinstance(actual, dict):
            all_keys = set(actual.keys()) | set(expected.keys())
            for key in all_keys:
                new_path = f"{path}.{key}" if path else key
                if key not in expected:
                    differences.append({"path": new_path, "type": "extra", "value": actual[key]})
                elif key not in actual:
                    differences.append({"path": new_path, "type": "missing", "value": expected[key]})
                else:
                    differences.extend(self._find_differences(actual[key], expected[key], new_path))

        elif isinstance(actual, (list, tuple)):
            for i in range(max(len(actual), len(expected))):
                new_path = f"{path}[{i}]"
                if i >= len(expected):
                    differences.append({"path": new_path, "type": "extra", "value": actual[i]})
                elif i >= len(actual):
                    differences.append({"path": new_path, "type": "missing", "value": expected[i]})
                else:
                    differences.extend(self._find_differences(actual[i], expected[i], new_path))

        elif actual != expected:
            differences.append({
                "path": path,
                "type": "mismatch",
                "expected": expected,
                "actual": actual,
            })

        return differences

    def update_golden_data(self, name: str, new_data: dict[str, Any], version: str | None = None) -> GoldenDataSet:
        """Update existing golden data with new version.

        Args:
            name: Name of golden data set
            new_data: New data values
            version: New version (auto-incremented if not specified)

        Returns:
            Updated GoldenDataSet
        """
        old_golden = self.load_golden_data(name)
        if old_golden:
            old_version = old_golden.version
            # Auto-increment version
            if version is None:
                try:
                    version_parts = old_version.split(".")
                    version_parts[-1] = str(int(version_parts[-1]) + 1)
                    version = ".".join(version_parts)
                except:
                    version = f"{old_version}.1"

        dataset = GoldenDataSet(
            name=name,
            data_type=old_golden.data_type if old_golden else GoldenDataType.EXPECTED_OUTPUT,
            version=version or "1.0",
            data=new_data,
            tags=old_golden.tags if old_golden else [],
            metadata={
                **(old_golden.metadata if old_golden else {}),
                "previous_version": old_golden.version if old_golden else None,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        self.save_golden_data(dataset)
        return dataset

    def create_test_snapshot(self, test_case_id: UUID, result: Any) -> GoldenDataSet:
        """Create a golden data snapshot from test result.

        Args:
            test_case_id: ID of the test case
            result: Test result to snapshot

        Returns:
            Created GoldenDataSet
        """
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                test = db.query(TestCase).filter(TestCase.id == test_case_id).first()
                if not test:
                    raise ValueError(f"Test case not found: {test_case_id}")

                name = f"test_{test_case_id}"
                version = "1.0"

                dataset = GoldenDataSet(
                    name=name,
                    data_type=GoldenDataType.EXPECTED_OUTPUT,
                    version=version,
                    data={"result": result} if not isinstance(result, dict) else result,
                    metadata={
                        "test_case_id": str(test_case_id),
                        "test_title": test.title,
                    },
                    tags=[test.type.value, test.priority.value],
                )

                self.save_golden_data(dataset)
                return dataset

            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to create test snapshot: {e}")
            raise

    def list_golden_data(self, data_type: GoldenDataType | None = None) -> list[GoldenDataSet]:
        """List all available golden data sets.

        Args:
            data_type: Optional filter by data type

        Returns:
            List of GoldenDataSet metadata
        """
        datasets = []

        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data_dict = json.load(f)

                dataset = GoldenDataSet(
                    name=data_dict["name"],
                    data_type=GoldenDataType(data_dict["data_type"]),
                    version=data_dict["version"],
                    data={},  # Don't load full data for listing
                    created_at=datetime.fromisoformat(data_dict["created_at"]),
                    metadata=data_dict.get("metadata", {}),
                    tags=data_dict.get("tags", []),
                )

                if data_type is None or dataset.data_type == data_type:
                    datasets.append(dataset)

            except Exception as e:
                logger.warning(f"Failed to load golden data {file_path}: {e}")

        return sorted(datasets, key=lambda d: d.created_at, reverse=True)


def get_golden_data_manager(storage_path: str | None = None) -> GoldenDataManager:
    """Get or create golden data manager instance."""
    return GoldenDataManager(storage_path)
