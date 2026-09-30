"""
Logic structures identification service - Story 1.20

Identifies and catalogs all logical structures in source code:
- Functions/methods: name, parameters, return type, visibility, complexity, LOC
- Classes/interfaces: name, attributes, methods, inheritance, interface implementations
- Modules/packages: name, exports, imports, relationships

Creates unified CodeStructureCatalog from parsed AST.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.core.database import get_sync_session
from app.models.analysis_result import AnalysisResult, AnalysisStatus
from app.services.analysis.ast.ast_tree import ASTTree
from app.services.analysis.ast.registry import ASTParserRegistry

logger = logging.getLogger(__name__)


class VisibilityLevel(StrEnum):
    """Visibility levels for code structures."""

    PUBLIC = "public"
    PROTECTED = "protected"
    PRIVATE = "private"
    INTERNAL = "internal"


@dataclass
class FunctionInfo:
    """Information about a function or method."""

    name: str
    parameters: list[dict]  # name, type, default
    return_type: str | None
    visibility: VisibilityLevel
    complexity: int
    loc: int  # lines of code
    line_start: int
    line_end: int
    docstring: str | None
    is_class_method: bool = False
    class_name: str | None = None
    file_path: str | None = None


@dataclass
class ClassInfo:
    """Information about a class or interface."""

    name: str
    attributes: list[dict]
    methods: list[FunctionInfo]
    bases: list[str]  # inheritance
    implements: list[str]  # interfaces
    is_interface: bool
    visibility: VisibilityLevel
    complexity: int
    loc: int
    line_start: int
    line_end: int
    docstring: str | None
    file_path: str | None = None


@dataclass
class ModuleInfo:
    """Information about a module/package."""

    name: str
    file_path: str
    imports: list[dict]
    exports: list[str]  # public functions/classes
    functions_count: int
    classes_count: int
    loc: int


@dataclass
class CodeStructureCatalog:
    """Unified catalog of all code structures."""

    language: str
    source_files: list[str] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    modules: list[ModuleInfo] = field(default_factory=list)
    total_loc: int = 0
    total_functions: int = 0
    total_classes: int = 0
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)

    def get_statistics(self) -> dict[str, Any]:
        """Calculate statistics for dashboard display."""
        complexity_by_function = [f.complexity for f in self.functions]
        avg_complexity = sum(complexity_by_function) / len(complexity_by_function) if complexity_by_function else 0

        complexity_levels = {
            "low": len([c for c in complexity_by_function if c <= 5]),
            "medium": len([c for c in complexity_by_function if 5 < c <= 10]),
            "high": len([c for c in complexity_by_function if c > 10]),
        }

        visibility_counts = {
            "public": len([f for f in self.functions if f.visibility == VisibilityLevel.PUBLIC]),
            "protected": len([f for f in self.functions if f.visibility == VisibilityLevel.PROTECTED]),
            "private": len([f for f in self.functions if f.visibility == VisibilityLevel.PRIVATE]),
            "internal": len([f for f in self.functions if f.visibility == VisibilityLevel.INTERNAL]),
        }

        return {
            "total_functions": self.total_functions,
            "total_classes": self.total_classes,
            "total_loc": self.total_loc,
            "source_files_count": len(self.source_files),
            "average_complexity": avg_complexity,
            "complexity_levels": complexity_levels,
            "visibility_distribution": visibility_counts,
        }

    def filter_by_complexity(self, level: str) -> "CodeStructureCatalog":
        """Filter structures by complexity level."""
        complexity_map = {"low": 5, "medium": 10, "high": float("inf")}
        threshold = complexity_map.get(level, float("inf"))

        filtered = CodeStructureCatalog(language=self.language)
        filtered.source_files = self.source_files.copy()
        filtered.functions = [f for f in self.functions if f.complexity <= threshold]
        filtered.classes = [c for c in self.classes if c.complexity <= threshold]
        # Filter modules to only include matching functions/classes
        # ... (implementation simplified for brevity)

        return filtered

    def filter_by_visibility(self, visibility: VisibilityLevel) -> "CodeStructureCatalog":
        """Filter structures by visibility level."""
        filtered = CodeStructureCatalog(language=self.language)
        filtered.source_files = self.source_files.copy()
        filtered.functions = [f for f in self.functions if f.visibility == visibility]
        filtered.classes = [c for c in self.classes if c.visibility == visibility]
        return filtered

    def to_dict(self) -> dict:
        """Convert catalog to dictionary for JSON serialization."""
        return {
            "language": self.language,
            "source_files": self.source_files,
            "functions": [
                {
                    "name": f.name,
                    "parameters": f.parameters,
                    "return_type": f.return_type,
                    "visibility": f.visibility,
                    "complexity": f.complexity,
                    "loc": f.loc,
                    "line_start": f.line_start,
                    "line_end": f.line_end,
                    "docstring": f.docstring,
                    "is_class_method": f.is_class_method,
                    "class_name": f.class_name,
                    "file_path": f.file_path,
                }
                for f in self.functions
            ],
            "classes": [
                {
                    "name": c.name,
                    "attributes": c.attributes,
                    "methods": [
                        {
                            "name": m.name,
                            "parameters": m.parameters,
                            "return_type": m.return_type,
                            "visibility": m.visibility,
                            "complexity": m.complexity,
                            "loc": m.loc,
                            "line_start": m.line_start,
                            "line_end": m.line_end,
                            "docstring": m.docstring,
                        }
                        for m in c.methods
                    ],
                    "bases": c.bases,
                    "implements": c.implements,
                    "is_interface": c.is_interface,
                    "visibility": c.visibility,
                    "complexity": c.complexity,
                    "loc": c.loc,
                    "line_start": c.line_start,
                    "line_end": c.line_end,
                    "docstring": c.docstring,
                    "file_path": c.file_path,
                }
                for c in self.classes
            ],
            "modules": [
                {
                    "name": m.name,
                    "file_path": m.file_path,
                    "imports": m.imports,
                    "exports": m.exports,
                    "functions_count": m.functions_count,
                    "classes_count": m.classes_count,
                    "loc": m.loc,
                }
                for m in self.modules
            ],
            "total_loc": self.total_loc,
            "total_functions": self.total_functions,
            "total_classes": self.total_classes,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
        }


class LogicStructuresAnalyzer:
    """Analyzes code logic structures and creates unified catalog."""

    def __init__(self):
        self.parser_registry = ASTParserRegistry.get_instance()

    def analyze_file(self, source_code: str, file_path: str, language: str) -> CodeStructureCatalog:
        """Analyze a single source file and extract structures."""
        try:
            parser = self.parser_registry.get_parser(language)
            ast_tree = parser.parse(source_code, file_path)
            return self._build_catalog(ast_tree, file_path)
        except Exception as e:
            logger.error(f"Failed to analyze {file_path}: {e}")
            return CodeStructureCatalog(language=language)

    def _build_catalog(self, ast_tree: ASTTree, file_path: str) -> CodeStructureCatalog:
        """Build code structure catalog from AST tree."""
        catalog = CodeStructureCatalog(language=ast_tree.language)

        # Convert AST functions to FunctionInfo
        for func_node in ast_tree.all_functions(include_nested=False):
            catalog.functions.append(self._convert_function(func_node, file_path))

        # Convert AST classes to ClassInfo
        for class_node in ast_tree.all_classes():
            class_info = self._convert_class(class_node, file_path)
            catalog.classes.append(class_info)

        # Create module info
        module_info = ModuleInfo(
            name=file_path.replace("\\", "/").split("/")[-1].split(".")[0],
            file_path=file_path,
            imports=[{"module": imp.module, "aliases": list(imp.aliases or [])} for imp in ast_tree.imports],
            exports=[f.name for f in ast_tree.functions if self._is_public(f)],
            functions_count=len(ast_tree.functions),
            classes_count=len(ast_tree.classes),
            loc=ast_tree.loc_count,
        )
        catalog.modules.append(module_info)
        catalog.source_files.append(file_path)
        catalog.total_loc += ast_tree.loc_count

        # Count nested functions separately
        nested_count = sum(len(f.children) for f in ast_tree.functions)
        catalog.total_functions = len(ast_tree.functions) + nested_count
        catalog.total_classes = len(ast_tree.classes)

        return catalog

    def _convert_function(self, func_node, file_path: str) -> FunctionInfo:
        """Convert AST FunctionNode to FunctionInfo."""
        # Determine visibility
        visibility = self._determine_visibility(func_node)

        # Calculate LOC (rough estimate from line range)
        loc = max(1, func_node.line_end - func_node.line_start)

        return FunctionInfo(
            name=func_node.name,
            parameters=[
                {
                    "name": p.name,
                    "type": p.type,
                    "default_value": p.default_value,
                    "line_start": p.line_start,
                }
                for p in func_node.parameters
            ],
            return_type=func_node.return_type,
            visibility=visibility,
            complexity=func_node.complexity,
            loc=loc,
            line_start=func_node.line_start,
            line_end=func_node.line_end,
            docstring=func_node.docstring,
            file_path=file_path,
        )

    def _convert_class(self, class_node, file_path: str) -> ClassInfo:
        """Convert AST ClassNode to ClassInfo."""
        # Determine if this is an interface (heuristic)
        is_interface = self._is_interface(class_node)

        # Convert methods
        methods = [self._convert_function(method, file_path) for method in class_node.methods]

        # Calculate LOC
        loc = max(1, class_node.line_end - class_node.line_start)

        return ClassInfo(
            name=class_node.name,
            attributes=[],  # TODO: extract attributes from AST
            methods=methods,
            bases=class_node.bases,
            implements=[],  # TODO: extract interface implementations
            is_interface=is_interface,
            visibility=VisibilityLevel.PUBLIC,  # Classes are typically public in most languages
            complexity=class_node.complexity,
            loc=loc,
            line_start=class_node.line_start,
            line_end=class_node.line_end,
            docstring=class_node.docstring,
            file_path=file_path,
        )

    def _determine_visibility(self, func_node) -> VisibilityLevel:
        """Determine visibility of a function/method."""
        name = func_node.name

        # Common patterns for private/internal
        if name.startswith("_"):
            return VisibilityLevel.PRIVATE
        if name.startswith("__") and name.endswith("__"):
            return VisibilityLevel.INTERNAL  # Python dunder

        # TODO: Add language-specific visibility detection
        return VisibilityLevel.PUBLIC

    def _is_interface(self, class_node) -> bool:
        """Heuristic to determine if a class is an interface."""
        # Interface indicators:
        # - Name contains "Interface" or ends with "able" (e.g., Runnable)
        # - All methods are abstract (no implementation)
        # - Has only abstract methods
        name = class_node.name.lower()
        return "interface" in name or name.endswith("able")

    def _is_public(self, func_node) -> bool:
        """Determine if a function is public (exported)."""
        # Public if not private/internal
        return not func_node.name.startswith("_")

    def analyze_project(
        self,
        source_files: list[dict],  # {file_path, content, language}
        project_id: int,
        save_to_db: bool = True,
    ) -> CodeStructureCatalog:
        """Analyze multiple source files and create unified catalog.

        Args:
            source_files: List of file dictionaries with file_path, content, language
            project_id: Project ID for database storage
            save_to_db: If False, skip internal _save_to_database (caller handles persistence)
        """
        unified_catalog = CodeStructureCatalog(language="multi")

        for file_info in source_files:
            try:
                file_catalog = self.analyze_file(
                    source_code=file_info["content"],
                    file_path=file_info["file_path"],
                    language=file_info["language"],
                )
                # Merge catalogs
                unified_catalog.source_files.extend(file_catalog.source_files)
                unified_catalog.functions.extend(file_catalog.functions)
                unified_catalog.classes.extend(file_catalog.classes)
                unified_catalog.modules.extend(file_catalog.modules)
                unified_catalog.total_loc += file_catalog.total_loc
            except Exception as e:
                logger.error(f"Failed to analyze {file_info.get('file_path')}: {e}")

        # Save to database (unless caller wants to handle persistence)
        if save_to_db:
            self._save_to_database(unified_catalog, project_id)

        return unified_catalog

    def _save_to_database(self, catalog: CodeStructureCatalog, project_id: int):
        """Save analysis results to database."""
        with get_sync_session() as db:
            result = AnalysisResult(
                project_id=project_id,
                module="logic_structures",
                status=AnalysisStatus.COMPLETED,
                result_data=catalog.to_dict(),
            )
            db.add(result)
            db.commit()


def get_logic_structures_analyzer() -> LogicStructuresAnalyzer:
    """Get or create logic structures analyzer instance."""
    return LogicStructuresAnalyzer()
