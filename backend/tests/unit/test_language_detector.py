"""Unit tests for LanguageDetector."""

import pytest

from app.services.project.language_detector import LanguageDetector


@pytest.fixture()
def detector():
    return LanguageDetector()


# --- detect_by_extension ---


class TestDetectByExtension:
    @pytest.mark.parametrize(
        "filename, expected",
        [
            ("main.py", "python"),
            ("script.PY", "python"),
            ("App.java", "java"),
            ("index.js", "javascript"),
            ("app.ts", "typescript"),
            ("widget.tsx", "typescript"),
            ("Component.jsx", "javascript"),
            ("Program.cs", "csharp"),
            ("main.c", "cpp"),
            ("utils.cpp", "cpp"),
            ("header.h", "cpp"),
            ("impl.hpp", "cpp"),
            ("server.go", "go"),
            ("app.rb", "ruby"),
            ("index.php", "php"),
            ("ViewController.swift", "swift"),
            ("MainActivity.kt", "kotlin"),
            ("README.md", None),
            ("data.json", None),
            ("Makefile", None),
            (".gitignore", None),
        ],
    )
    def test_extension_mapping(self, detector, filename, expected):
        assert detector.detect_by_extension(filename) == expected

    def test_unknown_extension_returns_none(self, detector):
        assert detector.detect_by_extension("file.xyz") is None


# --- detect_by_content ---


class TestDetectByContent:
    def test_python_keywords(self, detector):
        assert detector.detect_by_content("def hello():\n    print('hi')\n") == "python"

    def test_java_package(self, detector):
        assert detector.detect_by_content("package com.example;\npublic class App {}\n") == "java"

    def test_csharp_using(self, detector):
        assert detector.detect_by_content("using System;\nnamespace App {}\n") == "csharp"

    def test_cpp_include(self, detector):
        assert detector.detect_by_content("#include <iostream>\nint main() {}\n") == "cpp"

    def test_javascript_const(self, detector):
        assert detector.detect_by_content("const x = require('fs');\nconsole.log(x);\n") == "javascript"

    def test_go_package(self, detector):
        assert detector.detect_by_content('package main\nimport "fmt"\nfunc main() {}\n') == "go"

    def test_php_open_tag(self, detector):
        assert detector.detect_by_content("<?php\n$foo = 1;\necho $foo;\n") == "php"

    def test_empty_content_returns_none(self, detector):
        assert detector.detect_by_content("") is None

    def test_unrecognized_content_returns_none(self, detector):
        assert detector.detect_by_content("blah blah blah\n") is None


# --- detect (combined) ---


class TestDetect:
    def test_extension_takes_priority(self, detector):
        """Extension match should win over content heuristic."""
        content = "package main\nfunc main() {}"
        result = detector.detect("script.py", content)
        assert result == "python"

    def test_fallback_to_content(self, detector):
        """No extension match → content heuristic."""
        result = detector.detect("Makefile", "def hello():\n    pass\n")
        assert result == "python"

    def test_fallback_to_unknown(self, detector):
        result = detector.detect("data.bin", "\x00\x01\x02")
        assert result == "unknown"

    def test_no_extension_with_java_content(self, detector):
        result = detector.detect("build", "package com.example;\npublic class App {}\n")
        assert result == "java"
