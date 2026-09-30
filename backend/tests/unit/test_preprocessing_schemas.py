"""Unit tests for preprocessing Pydantic schemas."""

import uuid

import pytest

from app.schemas.preprocessing import (
    LanguageCount,
    PreprocessingReportResponse,
    SourceFileUpdate,
    UnknownFileResponse,
)


class TestSourceFileUpdate:
    def test_allows_detected_language_only(self):
        body = SourceFileUpdate(detected_language="python")
        assert body.detected_language == "python"
        assert body.detected_framework is None

    def test_allows_detected_framework_only(self):
        body = SourceFileUpdate(detected_framework="pytest")
        assert body.detected_framework == "pytest"
        assert body.detected_language is None

    def test_allows_both_fields(self):
        body = SourceFileUpdate(detected_language="java", detected_framework="junit5")
        assert body.detected_language == "java"
        assert body.detected_framework == "junit5"

    def test_empty_body_is_valid(self):
        body = SourceFileUpdate()
        assert body.detected_language is None
        assert body.detected_framework is None

    def test_invalid_language_raises(self):
        with pytest.raises(ValueError):
            SourceFileUpdate(detected_language="not_a_language_xyz")

    def test_invalid_framework_raises(self):
        with pytest.raises(ValueError):
            SourceFileUpdate(detected_framework="")


class TestLanguageCount:
    def test_fields(self):
        lc = LanguageCount(language="python", count=12, loc=3400)
        assert lc.language == "python"
        assert lc.count == 12
        assert lc.loc == 3400


class TestPreprocessingReportResponse:
    def test_full_response(self):
        report = PreprocessingReportResponse(
            project_id=uuid.uuid4(),
            languages=[
                LanguageCount(language="python", count=10, loc=2500),
                LanguageCount(language="javascript", count=5, loc=800),
            ],
            detected_frameworks=["pytest", "jest"],
            total_loc=3300,
            unknown_files=[
                UnknownFileResponse(filename="readme.xyz", file_id=uuid.uuid4()),
                UnknownFileResponse(filename="data.bin", file_id=uuid.uuid4()),
            ],
        )
        assert len(report.languages) == 2
        assert report.detected_frameworks == ["pytest", "jest"]
        assert report.total_loc == 3300
        assert len(report.unknown_files) == 2

    def test_empty_unknown_files(self):
        report = PreprocessingReportResponse(
            project_id=uuid.uuid4(),
            languages=[LanguageCount(language="python", count=1, loc=100)],
            detected_frameworks=["pytest"],
            total_loc=100,
            unknown_files=[],
        )
        assert report.unknown_files == []
