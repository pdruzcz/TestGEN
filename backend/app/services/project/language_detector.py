"""Language detection based on file extensions and content heuristics."""

from __future__ import annotations

import os
from pathlib import PurePosixPath

# Extension → canonical language name
EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".cs": "csharp",
    ".c": "cpp",
    ".cpp": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
}

# Content keyword patterns → language (checked in order, first match wins)
_CONTENT_PATTERNS: list[tuple[str, str]] = [
    ("<?php", "php"),  # Story 1.52 (FR12): PHP open tag — strong, unambiguous signal
    ("package main", "go"),
    ("func main()", "go"),
    ('import "fmt"', "go"),
    ("using System;", "csharp"),
    ("using UnityEngine;", "csharp"),
    ("#include <", "cpp"),
    ("namespace std", "cpp"),
    ("namespace ", "csharp"),
    ("package com.", "java"),
    ("public class ", "java"),
    ("protected void ", "java"),
    ("System.out.println", "java"),
    ("def ", "python"),
    ("import os", "python"),
    ("from typing", "python"),
    ("if __name__", "python"),
    ("const ", "javascript"),
    ("require(", "javascript"),
    ("module.exports", "javascript"),
    ("console.log", "javascript"),
    ("console.error", "javascript"),
]


class LanguageDetector:
    """Stateless language detector — thread-safe."""

    def detect_by_extension(self, filename: str) -> str | None:
        ext = os.path.splitext(filename)[1].lower()
        return EXTENSION_MAP.get(ext)

    def detect_by_content(self, content: str) -> str | None:
        if not content:
            return None
        head = content[:2000]
        for pattern, language in _CONTENT_PATTERNS:
            if pattern in head:
                return language
        return None

    def detect(self, file_path: str, content: str) -> str:
        filename = PurePosixPath(file_path).name
        by_ext = self.detect_by_extension(filename)
        if by_ext is not None:
            return by_ext
        by_content = self.detect_by_content(content)
        if by_content is not None:
            return by_content
        return "unknown"
