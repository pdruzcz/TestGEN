"""Unit tests for ArchiveExtractor."""

import os
import tarfile
import zipfile

import pytest

from app.services.project.archive_extractor import ArchiveExtractor


@pytest.fixture()
def extractor():
    return ArchiveExtractor()


def _write_files(directory: str, files: dict[str, str]) -> None:
    for name, content in files.items():
        path = os.path.join(directory, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def _make_zip(tmp: str, name: str, files: dict[str, str]) -> str:
    zip_path = os.path.join(tmp, name)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for fname, content in files.items():
            zf.writestr(fname, content)
    return zip_path


def _make_tar_gz(tmp: str, name: str, files: dict[str, str]) -> str:
    tar_path = os.path.join(tmp, name)
    with tarfile.open(tar_path, "w:gz") as tf:
        for fname, content in files.items():
            data = content.encode("utf-8")
            import io

            info = tarfile.TarInfo(name=fname)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return tar_path


class TestZipExtraction:
    def test_basic_zip(self, extractor, tmp_path):
        archive = _make_zip(
            str(tmp_path),
            "project.zip",
            {
                "src/main.py": "print('hello')",
                "src/utils.py": "def helper(): pass",
            },
        )
        target = os.path.join(str(tmp_path), "out")
        result = extractor.extract(archive, target)
        assert len(result) == 2
        assert any("main.py" in r for r in result)

    def test_zip_excludes_node_modules(self, extractor, tmp_path):
        archive = _make_zip(
            str(tmp_path),
            "project.zip",
            {
                "src/index.js": "console.log('hi')",
                "node_modules/lodash/index.js": "module.exports = {}",
            },
        )
        target = os.path.join(str(tmp_path), "out")
        result = extractor.extract(archive, target)
        assert len(result) == 1
        assert "node_modules" not in result[0]

    def test_zip_excludes_git(self, extractor, tmp_path):
        archive = _make_zip(
            str(tmp_path),
            "project.zip",
            {
                "main.py": "print('hi')",
                ".git/HEAD": "ref: refs/heads/main",
            },
        )
        target = os.path.join(str(tmp_path), "out")
        result = extractor.extract(archive, target)
        assert len(result) == 1
        assert ".git" not in result[0]

    def test_zip_excludes_binaries(self, extractor, tmp_path):
        archive = _make_zip(
            str(tmp_path),
            "project.zip",
            {
                "app.exe": "binary",
                "lib.dll": "binary",
                "main.py": "code",
            },
        )
        target = os.path.join(str(tmp_path), "out")
        result = extractor.extract(archive, target)
        assert len(result) == 1

    def test_zip_excludes_build_dirs(self, extractor, tmp_path):
        archive = _make_zip(
            str(tmp_path),
            "project.zip",
            {
                "src/app.py": "code",
                "build/output.o": "binary",
                "dist/package.whl": "binary",
                "__pycache__/mod.cpython.pyc": "bytecode",
            },
        )
        target = os.path.join(str(tmp_path), "out")
        result = extractor.extract(archive, target)
        assert len(result) == 1


class TestTarGzExtraction:
    def test_basic_tar_gz(self, extractor, tmp_path):
        archive = _make_tar_gz(
            str(tmp_path),
            "project.tar.gz",
            {
                "src/main.py": "print('hello')",
                "README.md": "# Hello",
            },
        )
        target = os.path.join(str(tmp_path), "out")
        result = extractor.extract(archive, target)
        assert len(result) == 2

    def test_tgz_extension(self, extractor, tmp_path):
        archive = _make_tar_gz(
            str(tmp_path),
            "project.tgz",
            {
                "main.py": "code",
            },
        )
        target = os.path.join(str(tmp_path), "out")
        result = extractor.extract(archive, target)
        assert len(result) == 1

    def test_tar_gz_excludes_excluded_dirs(self, extractor, tmp_path):
        archive = _make_tar_gz(
            str(tmp_path),
            "project.tar.gz",
            {
                "src/main.py": "code",
                "target/classes/App.class": "bytecode",
            },
        )
        target = os.path.join(str(tmp_path), "out")
        result = extractor.extract(archive, target)
        assert len(result) == 1


class TestZipBombProtection:
    def test_oversized_archive_raises(self, extractor, tmp_path):
        zip_path = _make_zip(
            str(tmp_path),
            "bomb.zip",
            {
                "huge.txt": "x" * 100,
            },
        )
        extractor.max_archive_size_mb = 0  # 0 MB limit forces failure
        target = os.path.join(str(tmp_path), "out")
        with pytest.raises(ValueError, match="exceeds"):
            extractor.extract(zip_path, target)


class TestDirectoryStructure:
    def test_preserves_relative_paths(self, extractor, tmp_path):
        archive = _make_zip(
            str(tmp_path),
            "project.zip",
            {
                "src/app/main.py": "code",
                "src/app/utils.py": "code",
            },
        )
        target = os.path.join(str(tmp_path), "out")
        result = extractor.extract(archive, target)
        assert len(result) == 2
        for r in result:
            assert "src" in r


class TestUnsupportedFormat:
    def test_unsupported_extension_raises(self, extractor, tmp_path):
        fake = os.path.join(str(tmp_path), "file.rar")
        with open(fake, "wb") as f:
            f.write(b"not a real archive")
        target = os.path.join(str(tmp_path), "out")
        with pytest.raises(ValueError, match="Unsupported"):
            extractor.extract(fake, target)


class TestAllowedExtensionsFilter:
    """Story 1.6-zakańczenie — archive contents filtered by allowed extensions.

    Disallowed extensions inside an archive are skipped (with a warning) rather
    than failing the whole extraction, so one stray asset does not sink a whole
    uploaded project.
    """

    def test_filters_out_disallowed_extensions(self, extractor, tmp_path):
        archive = _make_zip(
            str(tmp_path),
            "project.zip",
            {
                "src/index.php": "<?php echo 1;",
                "assets/logo.png": "PNG-bytes",  # not allowed, not in EXCLUDED set
            },
        )
        target = os.path.join(str(tmp_path), "out")
        result = extractor.extract(archive, target, allowed_extensions={".php"})
        assert len(result) == 1
        assert "index.php" in result[0]

    def test_keeps_unfiltered_when_allowed_extensions_omitted(self, extractor, tmp_path):
        # Backward-compat: callers that pass no allowed_extensions keep every
        # non-excluded file (existing document-extractor callers rely on this).
        archive = _make_zip(
            str(tmp_path),
            "project.zip",
            {
                "src/index.php": "<?php echo 1;",
                "assets/logo.png": "PNG-bytes",
            },
        )
        target = os.path.join(str(tmp_path), "out")
        result = extractor.extract(archive, target)
        assert len(result) == 2

    def test_filter_applies_to_tar_gz(self, extractor, tmp_path):
        archive = _make_tar_gz(
            str(tmp_path),
            "project.tar.gz",
            {
                "src/index.php": "<?php echo 1;",
                "assets/logo.png": "PNG-bytes",
            },
        )
        target = os.path.join(str(tmp_path), "out")
        result = extractor.extract(archive, target, allowed_extensions={".php"})
        assert len(result) == 1
        assert "index.php" in result[0]


class TestDecompressedSizeCap:
    """Story 1.6-zakańczenie — zip-bomb protection on decompressed total."""

    def test_extracted_size_over_cap_raises(self, extractor, tmp_path):
        archive = _make_zip(
            str(tmp_path),
            "bomb.zip",
            {"huge.txt": "x" * (200 * 1024)},  # 200 KiB decompressed
        )
        extractor.max_extracted_total_mb = 0  # 0 MiB cap → any content exceeds
        target = os.path.join(str(tmp_path), "out")
        with pytest.raises(ValueError, match=r"[Dd]ecompressed"):
            extractor.extract(archive, target)


class TestFileCountCap:
    """Story 1.6-zakańczenie — cap the number of files extracted from one archive."""

    def test_file_count_over_cap_raises(self, extractor, tmp_path):
        archive = _make_zip(
            str(tmp_path),
            "many.zip",
            {f"f{i}.py": "x" for i in range(5)},
        )
        extractor.max_file_count = 2
        target = os.path.join(str(tmp_path), "out")
        with pytest.raises(ValueError, match=r"count|exceeds"):
            extractor.extract(archive, target)
