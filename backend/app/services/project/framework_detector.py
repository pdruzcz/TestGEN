"""Framework detection based on project config files."""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


class FrameworkDetector:
    """Detects test framework from project configuration files."""

    def detect_framework(self, project_dir: str, language: str) -> str | None:
        if not os.path.isdir(project_dir):
            return None
        handler = {
            "python": self._detect_python,
            "javascript": self._detect_js,
            "typescript": self._detect_js,
            "java": self._detect_java,
            "csharp": self._detect_csharp,
            "cpp": self._detect_cpp,
            "php": self._detect_php,
        }.get(language)
        if handler is None:
            return None
        return handler(project_dir)

    # --- Python ---

    def _detect_python(self, d: str) -> str | None:
        req = os.path.join(d, "requirements.txt")
        if os.path.isfile(req):
            text = self._read(req)
            if "pytest" in text:
                return "pytest"
            if "nose2" in text:
                return "nose2"
            if "unittest" in text:
                return "unittest"

        pyproject = os.path.join(d, "pyproject.toml")
        if os.path.isfile(pyproject):
            text = self._read(pyproject)
            if "[tool.pytest" in text or "pytest-cov" in text:
                return "pytest"

        setup_cfg = os.path.join(d, "setup.cfg")
        if os.path.isfile(setup_cfg):
            text = self._read(setup_cfg)
            if "pytest" in text:
                return "pytest"
            if "unittest" in text:
                return "unittest"

        return None

    # --- JavaScript / TypeScript ---

    def _detect_js(self, d: str) -> str | None:
        pkg_path = os.path.join(d, "package.json")
        if not os.path.isfile(pkg_path):
            return None
        try:
            with open(pkg_path, encoding="utf-8") as f:
                pkg = json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to parse %s", pkg_path)
            return None

        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        for name in ("vitest", "jest", "mocha"):
            if name in deps:
                return name
        return None

    # --- Java ---

    def _detect_java(self, d: str) -> str | None:
        pom = os.path.join(d, "pom.xml")
        if os.path.isfile(pom):
            text = self._read(pom)
            if "junit-jupiter" in text or "org.junit.jupiter" in text:
                return "junit5"
            if "junit" in text:
                return "junit4"
            if "testng" in text:
                return "testng"

        gradle = os.path.join(d, "build.gradle")
        if os.path.isfile(gradle):
            text = self._read(gradle)
            if "junit-jupiter" in text or "junit5" in text:
                return "junit5"
            if "junit" in text:
                return "junit4"
            if "testng" in text:
                return "testng"

        return None

    # --- C# ---

    def _detect_csharp(self, d: str) -> str | None:
        for fname in os.listdir(d):
            if fname.endswith(".csproj") or fname.endswith(".fsproj"):
                text = self._read(os.path.join(d, fname))
                lower = text.lower()
                if "xunit" in lower:
                    return "xunit"
                if "nunit" in lower:
                    return "nunit"
                if "mstest" in lower:
                    return "mstest"
        return None

    # --- C/C++ ---

    def _detect_cpp(self, d: str) -> str | None:
        cmake = os.path.join(d, "CMakeLists.txt")
        if os.path.isfile(cmake):
            text = self._read(cmake)
            if "GTest" in text or "gtest" in text:
                return "gtest"
            if "Catch2" in text or "catch2" in text:
                return "catch2"

        makefile = os.path.join(d, "Makefile")
        if os.path.isfile(makefile):
            text = self._read(makefile)
            if "gtest" in text:
                return "gtest"
            if "catch2" in text:
                return "catch2"

        return None

    # --- PHP (Story 1.52, FR12) ---

    def _detect_php(self, d: str) -> str | None:
        """Detect PHP test framework from ``composer.json`` (require / require-dev)."""
        composer = os.path.join(d, "composer.json")
        if not os.path.isfile(composer):
            return None
        try:
            with open(composer, encoding="utf-8") as f:
                pkg = json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to parse %s", composer)
            return None

        deps = {**pkg.get("require", {}), **pkg.get("require-dev", {})}
        for name in ("pestphp/pest", "pestphp/pest-plugin"):
            if name in deps:
                return "pest"
        for name in ("phpunit/phpunit", "phpunit/phpunit-"):
            if name in deps:
                return "phpunit"
        # Fall back to a substring sweep for custom/dev fork package names.
        for dep_name in deps:
            if "pest" in dep_name:
                return "pest"
            if "phpunit" in dep_name:
                return "phpunit"
        return None

    # --- helpers ---

    @staticmethod
    def _read(path: str) -> str:
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                return f.read()
        except OSError:
            return ""
