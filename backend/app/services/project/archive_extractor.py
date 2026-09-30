"""Archive extraction with filtering of excluded directories and binaries.

Story 1.6-zakańczenie hardening:

* Optional ``allowed_extensions`` filter — entries whose extension is not on the
  allow-list are skipped with a warning rather than failing the whole archive,
  so one stray asset inside an uploaded project does not sink the rest.
* Zip-bomb protection on the **decompressed** payload — a capped total
  decompressed size (``max_extracted_total_mb``) and a capped file count
  (``max_file_count``), validated up-front before anything is written to disk.

Existing document-extractor callers (``db_schema_extractor`` & friends) keep
working unchanged: they call ``extract`` without ``allowed_extensions`` and the
defaults are generous enough that real document archives are unaffected.
"""

from __future__ import annotations

import logging
import os
import tarfile
import zipfile

logger = logging.getLogger(__name__)

EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        ".git",
        "__pycache__",
        "build",
        "dist",
        ".venv",
        "venv",
        "target",
        "bin",
        "obj",
    }
)

EXCLUDED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".pyc",
        ".class",
        ".o",
    }
)

# Candidate entry: ``(relative_path, uncompressed_size)``.
_Candidate = tuple[str, int]


class ArchiveExtractor:
    """Extracts archives while filtering unwanted files and directories."""

    def __init__(
        self,
        *,
        max_archive_size_mb: int = 500,
        max_extracted_total_mb: int = 1024,
        max_file_count: int = 10000,
    ) -> None:
        self.max_archive_size_mb = max_archive_size_mb
        self.max_extracted_total_mb = max_extracted_total_mb
        self.max_file_count = max_file_count

    def extract(
        self,
        archive_path: str,
        target_dir: str,
        *,
        allowed_extensions: frozenset[str] | set[str] | None = None,
    ) -> list[str]:
        """Extract ``archive_path`` into ``target_dir``.

        When ``allowed_extensions`` is provided, entries whose extension is not
        in the set are skipped (warned), not written. Returns the list of
        relative paths that were actually extracted.
        """
        self._validate_size(archive_path)

        os.makedirs(target_dir, exist_ok=True)
        ext = os.path.splitext(archive_path)[1].lower()

        if ext == ".zip":
            extracted = self._extract_zip(archive_path, target_dir, allowed_extensions)
        elif ext in (".gz", ".tgz", ".tar"):
            extracted = self._extract_tar(archive_path, target_dir, allowed_extensions)
        else:
            raise ValueError(f"Unsupported archive format: {ext}")

        logger.info("Extracted %d files from %s", len(extracted), archive_path)
        return extracted

    def _validate_size(self, archive_path: str) -> None:
        size_bytes = os.path.getsize(archive_path)
        size_mb = size_bytes / (1024 * 1024)
        if size_mb > self.max_archive_size_mb:
            raise ValueError(f"Archive size ({size_mb:.1f} MB) exceeds limit ({self.max_archive_size_mb} MB)")

    def _enforce_limits(self, candidates: list[_Candidate]) -> None:
        """Raise if the decompressed payload breaches the count or size caps."""
        count = len(candidates)
        if count > self.max_file_count:
            raise ValueError(f"File count ({count}) exceeds limit ({self.max_file_count})")
        total = sum(size for _, size in candidates)
        limit_bytes = self.max_extracted_total_mb * 1024 * 1024
        if total > limit_bytes:
            total_mb = total / (1024 * 1024)
            raise ValueError(f"Decompressed size ({total_mb:.1f} MB) exceeds limit ({self.max_extracted_total_mb} MB)")

    @staticmethod
    def _ext_allowed(name: str, allowed_extensions: frozenset[str] | set[str] | None) -> bool:
        if allowed_extensions is None:
            return True
        _, ext = os.path.splitext(name)
        return ext.lower() in allowed_extensions

    def _is_excluded(self, rel_path: str) -> bool:
        parts = rel_path.replace("\\", "/").split("/")
        for part in parts:
            if part in EXCLUDED_DIRS:
                return True
        _, ext = os.path.splitext(rel_path)
        return ext.lower() in EXCLUDED_EXTENSIONS

    def _is_path_traversal(self, rel_path: str, target_dir: str) -> bool:
        """Reject paths that escape the target directory (Zip Slip protection)."""
        dest = os.path.normpath(os.path.join(target_dir, rel_path))
        return not dest.startswith(os.path.abspath(target_dir) + os.sep)

    def _extract_zip(
        self,
        archive_path: str,
        target_dir: str,
        allowed_extensions: frozenset[str] | set[str] | None,
    ) -> list[str]:
        extracted: list[str] = []
        with zipfile.ZipFile(archive_path, "r") as zf:
            candidates: list[tuple[zipfile.ZipInfo, int]] = []
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if self._is_excluded(info.filename):
                    continue
                if self._is_path_traversal(info.filename, target_dir):
                    logger.warning("Skipping path-traversal entry: %s", info.filename)
                    continue
                if not self._ext_allowed(info.filename, allowed_extensions):
                    logger.warning("Skipping disallowed-extension entry: %s", info.filename)
                    continue
                candidates.append((info, info.file_size))

            self._enforce_limits([(c.filename, size) for c, size in candidates])

            for info, _size in candidates:
                dest = os.path.join(target_dir, info.filename)
                parent = os.path.dirname(dest)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with zf.open(info) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                extracted.append(info.filename)
        return extracted

    def _extract_tar(
        self,
        archive_path: str,
        target_dir: str,
        allowed_extensions: frozenset[str] | set[str] | None,
    ) -> list[str]:
        mode = "r:" if archive_path.lower().endswith(".tar") else "r:gz"
        extracted: list[str] = []
        with tarfile.open(archive_path, mode) as tf:
            candidates: list[tuple[tarfile.TarInfo, int]] = []
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                if self._is_excluded(member.name):
                    continue
                if self._is_path_traversal(member.name, target_dir):
                    logger.warning("Skipping path-traversal entry: %s", member.name)
                    continue
                if not self._ext_allowed(member.name, allowed_extensions):
                    logger.warning("Skipping disallowed-extension entry: %s", member.name)
                    continue
                candidates.append((member, member.size))

            self._enforce_limits([(m.name, size) for m, size in candidates])

            for member, _size in candidates:
                dest = os.path.join(target_dir, member.name)
                parent = os.path.dirname(dest)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with tf.extractfile(member) as src, open(dest, "wb") as dst:
                    if src is not None:
                        dst.write(src.read())
                extracted.append(member.name)
        return extracted
