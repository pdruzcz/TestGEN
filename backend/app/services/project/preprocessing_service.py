"""Preprocessing orchestration: language detection, framework detection, LOC counting."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.models.source_file import SourceFile
from app.services.project.framework_detector import FrameworkDetector
from app.services.project.language_detector import LanguageDetector

logger = logging.getLogger(__name__)

_CACHE_TTL = 3600  # 1 hour
_MAX_CONTENT_BYTES = 1 * 1024 * 1024  # 1MB — larger files skip content download
_AVG_BYTES_PER_LOC = 30  # rough estimate for LOC when content is unavailable

_CONFIG_FILE_NAMES = frozenset(
    {
        "package.json",
        "pom.xml",
        "build.gradle",
        "pyproject.toml",
        "requirements.txt",
        "setup.cfg",
        "CMakeLists.txt",
        "Makefile",
        "composer.json",  # Story 1.52 (FR12): PHP framework detection
    }
)

_CONFIG_FILE_EXTENSIONS = frozenset({".csproj", ".fsproj"})


@dataclass
class LanguageStat:
    language: str
    count: int = 0
    loc: int = 0


@dataclass
class UnknownFile:
    filename: str
    file_id: uuid.UUID


@dataclass
class PreprocessingReport:
    project_id: uuid.UUID
    languages: list[LanguageStat] = field(default_factory=list)
    detected_frameworks: list[str] = field(default_factory=list)
    total_loc: int = 0
    unknown_files: list[UnknownFile] = field(default_factory=list)


class PreprocessingService:
    """Orchestrates the preprocessing pipeline for a project."""

    def __init__(self) -> None:
        self._language_detector = LanguageDetector()
        self._framework_detector = FrameworkDetector()

    async def run_preprocessing(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> PreprocessingReport:
        result = await db.execute(
            select(SourceFile).where(
                SourceFile.project_id == project_id,
                SourceFile.is_cleaned_up.is_(False),
            )
        )
        files = list(result.scalars().all())

        if not files:
            report = PreprocessingReport(project_id=project_id)
            await self._cache_report_safe(report)
            return report

        lang_stats: dict[str, LanguageStat] = {}
        unknown_files: list[UnknownFile] = []
        project_languages: set[str] = set()
        total_loc = 0

        for sf in files:
            content = await self._read_file_content(sf)
            language = self._language_detector.detect(sf.filename, content or "")
            sf.detected_language = language

            loc = self._count_loc(content) if content is not None else self._estimate_loc(sf.file_size)
            sf.loc_count = loc
            total_loc += loc

            if language == "unknown":
                sf.requires_manual_classification = True
                unknown_files.append(UnknownFile(filename=sf.filename, file_id=sf.id))
            else:
                project_languages.add(language)
                stat = lang_stats.setdefault(language, LanguageStat(language=language))
                stat.count += 1
                stat.loc += loc

        project_dir = await self._prepare_project_dir(files)
        frameworks: list[str] = []
        try:
            for lang in project_languages:
                fw = self._framework_detector.detect_framework(project_dir or ".", lang)
                if fw and fw not in frameworks:
                    frameworks.append(fw)
                    for sf in files:
                        if sf.detected_language == lang:
                            sf.detected_framework = fw
        finally:
            if project_dir:
                shutil.rmtree(project_dir, ignore_errors=True)

        await db.flush()

        report = PreprocessingReport(
            project_id=project_id,
            languages=sorted(lang_stats.values(), key=lambda s: s.count, reverse=True),
            detected_frameworks=frameworks,
            total_loc=total_loc,
            unknown_files=unknown_files,
        )
        await self._cache_report_safe(report)
        return report

    async def get_cached_report(self, project_id: uuid.UUID) -> PreprocessingReport | None:
        try:
            redis = await get_redis()
            data = await redis.get(f"preprocessing:{project_id}")
        except Exception:
            logger.warning("Redis unavailable for cached report lookup")
            return None
        if not data:
            return None
        raw = json.loads(data)
        return PreprocessingReport(
            project_id=uuid.UUID(raw["project_id"]),
            languages=[LanguageStat(**ls) for ls in raw.get("languages", [])],
            detected_frameworks=raw.get("detected_frameworks", []),
            total_loc=raw.get("total_loc", 0),
            unknown_files=[
                UnknownFile(filename=uf["filename"], file_id=uuid.UUID(uf["file_id"]))
                for uf in raw.get("unknown_files", [])
            ],
        )

    async def _cache_report_safe(self, report: PreprocessingReport) -> None:
        """Cache report in Redis — failures are logged but do not break the pipeline."""
        try:
            redis = await get_redis()
            payload = json.dumps(
                {
                    "project_id": str(report.project_id),
                    "languages": [
                        {"language": ls.language, "count": ls.count, "loc": ls.loc} for ls in report.languages
                    ],
                    "detected_frameworks": report.detected_frameworks,
                    "total_loc": report.total_loc,
                    "unknown_files": [
                        {"filename": uf.filename, "file_id": str(uf.file_id)} for uf in report.unknown_files
                    ],
                }
            )
            await redis.set(f"preprocessing:{report.project_id}", payload, ex=_CACHE_TTL)
        except Exception:
            logger.warning("Failed to cache preprocessing report for project %s", report.project_id)

    async def _read_file_content(self, sf: SourceFile) -> str | None:
        """Download file content from MinIO. Returns None for large files or on error."""
        if sf.file_size > _MAX_CONTENT_BYTES:
            return None

        from app.core.config import get_settings
        from app.core.storage import download_file_bytes

        settings = get_settings()
        try:
            data = await asyncio.to_thread(
                download_file_bytes,
                settings.minio_bucket_name,
                sf.storage_key,
            )
            return data.decode("utf-8", errors="replace")
        except Exception:
            logger.warning("Failed to read content for %s (key=%s)", sf.filename, sf.storage_key)
            return None

    async def _prepare_project_dir(self, files: list[SourceFile]) -> str | None:
        """Download config files to a temp directory for framework detection.

        Preserves relative directory structure via ``original_path`` to avoid
        name collisions when multiple sub-projects contain the same config file.
        """
        config_files = [
            f
            for f in files
            if f.filename in _CONFIG_FILE_NAMES or os.path.splitext(f.filename)[1].lower() in _CONFIG_FILE_EXTENSIONS
        ]
        if not config_files:
            return None

        tmpdir = tempfile.mkdtemp(prefix="preprocessing_")
        for sf in config_files:
            content = await self._read_file_content(sf)
            if content is not None:
                rel = getattr(sf, "original_path", None) or sf.filename
                dest = os.path.join(tmpdir, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(content)
        return tmpdir

    @staticmethod
    def _count_loc(content: str) -> int:
        return sum(1 for line in content.splitlines() if line.strip())

    @staticmethod
    def _estimate_loc(file_size: int) -> int:
        """Rough LOC estimate for large files whose content was not downloaded."""
        if file_size <= 0:
            return 0
        return max(1, file_size // _AVG_BYTES_PER_LOC)
