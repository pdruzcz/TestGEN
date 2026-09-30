"""
Entry points and API endpoints identification service - Story 1.21

Identifies entry points and API endpoints per framework:
- Python: Flask @app.route, FastAPI @router.get, Django views, main()
- Java: Spring @RestController, JAX-RS @Path, main()
- JS/TS: Express app.get, NestJS @Controller, Angular routing
- C#: ASP.NET [HttpGet], minimal API app.MapGet
- C/C++: main(), DLL exports

Creates endpoints catalog with HTTP method, path, parameters, return type.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.core.database import get_sync_session
from app.models.analysis_result import AnalysisResult, AnalysisStatus
from app.services.analysis.ast.ast_tree import ASTTree
from app.services.analysis.ast.registry import ASTParserRegistry

logger = logging.getLogger(__name__)


class HTTPMethod(StrEnum):
    """HTTP methods for API endpoints."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    TRACE = "TRACE"


class EntryPointType(StrEnum):
    """Types of entry points."""

    API_ENDPOINT = "api_endpoint"
    MAIN_FUNCTION = "main_function"
    PUBLIC_FUNCTION = "public_function"
    DLL_EXPORT = "dll_export"
    FRAMEWORK_SPECIFIC = "framework_specific"
    UNKNOWN = "unknown"


@dataclass
class ParameterInfo:
    """Information about a parameter."""

    name: str
    type: str | None
    location: str  # query, path, body, header
    required: bool = False
    default_value: Any | None = None


@dataclass
class EndpointInfo:
    """Information about an API endpoint."""

    http_method: HTTPMethod | None
    path: str
    name: str | None
    parameters: list[ParameterInfo]
    return_type: str | None
    entry_type: EntryPointType
    framework: str | None = None
    file_path: str | None = None
    line_start: int | None = None
    middleware: list[str] = field(default_factory=list)


@dataclass
class EntryPointCatalog:
    """Catalog of all entry points and API endpoints."""

    language: str
    source_files: list[str] = field(default_factory=list)
    endpoints: list[EndpointInfo] = field(default_factory=list)
    main_functions: list[dict] = field(default_factory=list)
    public_functions: list[dict] = field(default_factory=list)
    framework_detected: bool = False
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)

    def get_statistics(self) -> dict[str, Any]:
        """Calculate statistics for dashboard."""
        endpoints_by_method = {}
        for ep in self.endpoints:
            if ep.http_method:
                endpoints_by_method[ep.http_method] = endpoints_by_method.get(ep.http_method, 0) + 1

        return {
            "total_endpoints": len(self.endpoints),
            "framework_detected": self.framework_detected,
            "endpoints_by_method": endpoints_by_method,
            "main_functions_count": len(self.main_functions),
            "public_functions_count": len(self.public_functions),
        }

    def to_dict(self) -> dict:
        """Convert catalog to dictionary for JSON serialization."""
        return {
            "language": self.language,
            "source_files": self.source_files,
            "endpoints": [
                {
                    "http_method": ep.http_method,
                    "path": ep.path,
                    "name": ep.name,
                    "parameters": [
                        {
                            "name": p.name,
                            "type": p.type,
                            "location": p.location,
                            "required": p.required,
                            "default_value": str(p.default_value) if p.default_value else None,
                        }
                        for p in ep.parameters
                    ],
                    "return_type": ep.return_type,
                    "middleware": ep.middleware,
                    "entry_type": ep.entry_type,
                    "framework": ep.framework,
                    "file_path": ep.file_path,
                    "line_start": ep.line_start,
                }
                for ep in self.endpoints
            ],
            "main_functions": self.main_functions,
            "public_functions": self.public_functions,
            "framework_detected": self.framework_detected,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "statistics": self.get_statistics(),
        }


class EntryPointsAnalyzer:
    """Analyzes code to identify entry points and API endpoints."""

    def __init__(self):
        self.parser_registry = ASTParserRegistry.get_instance()

        # Framework-specific patterns per language
        self._framework_patterns = {
            "python": {
                "flask": [
                    (r"@app\.route\((?:[^)]+)\)", ["GET", "POST", "PUT", "DELETE", "PATCH"]),
                    (r"@app\.(?:get|post|put|delete|patch)\((?:[^)]+)\)", ["GET", "POST", "PUT", "DELETE", "PATCH"]),
                ],
                "fastapi": [
                    (r"@router\.(?:get|post|put|delete|patch)\((?:[^)]+)\)", ["GET", "POST", "PUT", "DELETE", "PATCH"]),
                ],
                "django": [
                    (r"def\s+(\w+)\s*\(\s*request\s*:", None),  # view functions
                ],
            },
            "java": {
                "spring": [
                    (r"@(?:Get|Post|Put|Delete|Patch)Mapping\((?:[^)]+)\)", ["GET", "POST", "PUT", "DELETE", "PATCH"]),
                    (r"@RestController", None),
                    (r"@RequestMapping\((?:[^)]+)\)", None),
                ],
                "jax-rs": [
                    (r"@Path\s*\(\s*['\"]([^'\"]*)", None),
                ],
            },
            "javascript": {
                "express": [
                    (
                        r"(?:app\.)?(?:get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]*)",
                        ["GET", "POST", "PUT", "DELETE", "PATCH"],
                    ),
                ],
            },
            "typescript": {
                "nestjs": [
                    (r"@Controller\(\s*['\"]([^'\"]*)", None),
                    (r"@Get\s*\(\s*['\"]([^'\"]*)", ["GET"]),
                    (r"@Post\s*\(\s*['\"]([^'\"]*)", ["POST"]),
                ],
            },
            "csharp": {
                "aspnet": [
                    (r"\[Http(?:Get|Post|Put|Delete|Patch)\]", ["GET", "POST", "PUT", "DELETE", "PATCH"]),
                ],
                "minimal": [
                    (r"app\.Map(?:Get|Post|Put|Delete|Patch)", ["GET", "POST", "PUT", "DELETE", "PATCH"]),
                ],
            },
            "cpp": {},
            "php": {
                # Laravel / Symfony PHP 8 route attributes: #[Route(...)], #[Get(...)], ...
                # Detection matches the opening of the attribute; arguments may nest
                # array literals ([...]) so we do not bound them here.
                "laravel": [
                    (r"#\[\s*(?:Route|Get|Post|Put|Delete|Patch|Head|Options)\s*\(", None),
                    (
                        r"Route::(?:get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]*)",
                        ["GET", "POST", "PUT", "DELETE", "PATCH"],
                    ),
                ],
                "symfony": [
                    (r"#\[\s*Route\s*\(", None),
                ],
            },
        }

    def analyze_file(self, source_code: str, file_path: str, language: str) -> EntryPointCatalog:
        """Analyze a single file for entry points."""
        catalog = EntryPointCatalog(language=language)

        try:
            parser = self.parser_registry.get_parser(language)
            ast_tree = parser.parse(source_code, file_path)

            # Detect framework and extract endpoints
            framework, endpoints = self._extract_endpoints(source_code, file_path, language, ast_tree)
            catalog.framework_detected = framework is not None
            catalog.endpoints = endpoints

            # Find main function
            main_funcs = self._find_main_functions(ast_tree)
            catalog.main_functions = main_funcs

            # Find public functions (no internal callers)
            public_funcs = self._find_public_functions(ast_tree)
            catalog.public_functions = public_funcs

            catalog.source_files.append(file_path)

        except Exception as e:
            logger.error(f"Failed to analyze entry points in {file_path}: {e}")

        return catalog

    def _extract_endpoints(
        self, source_code: str, file_path: str, language: str, ast_tree: ASTTree
    ) -> tuple[str | None, list[EndpointInfo]]:
        """Extract endpoints based on framework detection."""
        patterns = self._framework_patterns.get(language, {})

        # Try to detect framework by searching for patterns
        detected_framework = None
        for framework_name, framework_patterns in patterns.items():
            for pattern, _methods in framework_patterns:
                if re.search(pattern, source_code):
                    detected_framework = framework_name
                    break
            if detected_framework:
                break

        endpoints = []

        if detected_framework:
            endpoints = self._extract_framework_endpoints(source_code, file_path, language, detected_framework)
        else:
            # Fallback: heuristic entry points
            endpoints = self._extract_heuristic_endpoints(ast_tree, file_path)

        return detected_framework, endpoints

    def _extract_framework_endpoints(
        self, source_code: str, file_path: str, language: str, framework: str
    ) -> list[EndpointInfo]:
        """Extract endpoints for a specific framework."""
        endpoints = []
        patterns = self._framework_patterns[language][framework]

        if language == "python" and framework == "flask":
            endpoints = self._extract_flask_endpoints(source_code, file_path, patterns)
        elif language == "python" and framework == "fastapi":
            endpoints = self._extract_fastapi_endpoints(source_code, file_path, patterns)
        elif language == "java" and framework == "spring":
            endpoints = self._extract_spring_endpoints(source_code, file_path, patterns)
        elif language == "php" and framework in ("laravel", "symfony"):
            endpoints = self._extract_php_endpoints(source_code, file_path)
        # TODO: Add more framework implementations

        return endpoints

    def _extract_php_endpoints(self, source_code: str, file_path: str) -> list[EndpointInfo]:
        """Extract PHP (Laravel/Symfony) endpoints from #[Route] attributes and Route:: calls.

        Story 1.52 (FR12) — closes PHP entry-point detection.
        """
        endpoints: list[EndpointInfo] = []

        # PHP 8 route attributes: #[Route('/x', methods: ['GET'])], #[Get('/x')], ...
        # Non-greedy args capture up to the attribute's closing )]; array literals
        # inside the argument list are tolerated by the lazy match.
        attr_re = re.compile(
            r"#\[\s*(?P<verb>Route|Get|Post|Put|Delete|Patch|Head|Options)\s*\((?P<args>.*?)\)\s*\]",
            re.IGNORECASE | re.DOTALL,
        )
        for match in attr_re.finditer(source_code):
            verb = match.group("verb").lower()
            args = match.group("args")
            path = self._php_route_path(args)
            method = self._php_route_method(verb, args)
            framework = "Symfony" if verb == "route" and "symfony" in source_code.lower() else "Laravel"
            endpoints.append(
                EndpointInfo(
                    http_method=method,
                    path=path,
                    name=None,
                    parameters=[],
                    return_type=None,
                    middleware=[],
                    entry_type=EntryPointType.API_ENDPOINT,
                    framework=framework,
                    file_path=file_path,
                    line_start=source_code.count("\n", 0, match.start()) + 1,
                )
            )

        # Laravel route definition files: Route::get('/path', [Controller::class, 'method'])
        static_re = re.compile(
            r"Route::(?P<verb>get|post|put|delete|patch)\s*\(\s*['\"](?P<path>[^'\"]+)",
            re.IGNORECASE,
        )
        for match in static_re.finditer(source_code):
            verb = match.group("verb").lower()
            try:
                method = HTTPMethod[verb.upper()]
            except KeyError:
                method = None
            endpoints.append(
                EndpointInfo(
                    http_method=method,
                    path=match.group("path"),
                    name=None,
                    parameters=[],
                    return_type=None,
                    middleware=[],
                    entry_type=EntryPointType.API_ENDPOINT,
                    framework="Laravel",
                    file_path=file_path,
                    line_start=source_code.count("\n", 0, match.start()) + 1,
                )
            )

        return endpoints

    @staticmethod
    def _php_route_path(args: str) -> str:
        """Pull the path out of a #[Route(...)] argument list."""
        named = re.search(r"path\s*:\s*['\"]([^'\"]+)", args)
        if named:
            return named.group(1)
        positional = re.search(r"['\"]([^'\"]+)", args)
        return positional.group(1) if positional else "/"

    @staticmethod
    def _php_route_method(verb: str, args: str) -> HTTPMethod | None:
        """Resolve the HTTP method for a #[Route] / #[Get] attribute."""
        if verb in ("get", "post", "put", "delete", "patch", "head", "options"):
            try:
                return HTTPMethod[verb.upper()]
            except KeyError:
                return None
        # #[Route(methods: ['GET'])] — pull the method from the methods list.
        methods_match = re.search(r"methods\s*:\s*\[?\s*['\"](\w+)", args)
        if methods_match:
            try:
                return HTTPMethod[methods_match.group(1).upper()]
            except KeyError:
                return None
        return None

    def _extract_flask_endpoints(self, source_code: str, file_path: str, patterns: list) -> list[EndpointInfo]:
        """Extract Flask endpoints."""
        endpoints = []

        for pattern, methods in patterns:
            for match in re.finditer(pattern, source_code, re.MULTILINE):
                try:
                    route_match = re.search(r"\(([^)]+)\)", match.group(1) or "")
                    path = route_match.group(1).strip("'\"") if route_match else "/"

                    func_name_match = re.search(r"def\s+(\w+)\s*\(", match.group(0)[match.end() :])
                    func_name = func_name_match.group(1) if func_name_match else None

                    endpoints.append(
                        EndpointInfo(
                            http_method=HTTPMethod.GET if len(methods) == 1 else None,  # Simplified
                            path=path,
                            name=func_name,
                            parameters=[],  # TODO: extract parameters
                            return_type=None,  # TODO: extract return type
                            middleware=[],
                            entry_type=EntryPointType.API_ENDPOINT,
                            framework="Flask",
                            file_path=file_path,
                            line_start=match.start() + 1,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to parse Flask endpoint: {e}")

        return endpoints

    def _extract_fastapi_endpoints(self, source_code: str, file_path: str, patterns: list) -> list[EndpointInfo]:
        """Extract FastAPI endpoints."""
        endpoints = []

        for pattern, _methods in patterns:
            for match in re.finditer(pattern, source_code, re.MULTILINE):
                try:
                    matched_text = match.group(0)
                    # Extract path from @router.get("/path") or @router.get("/path", ...)
                    path_match = re.search(r"\(([^,)]+)", matched_text)
                    path = path_match.group(1).strip("'\"") if path_match else "/"

                    # Extract method from pattern
                    method_match = re.search(r"\.(get|post|put|delete|patch)\(", matched_text)
                    method_name = method_match.group(1) if method_match else "get"
                    http_method = HTTPMethod[method_name.upper()]

                    endpoints.append(
                        EndpointInfo(
                            http_method=http_method,
                            path=path,
                            name=None,
                            parameters=[],
                            return_type=None,
                            middleware=[],
                            entry_type=EntryPointType.API_ENDPOINT,
                            framework="FastAPI",
                            file_path=file_path,
                            line_start=match.start() + 1,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to parse FastAPI endpoint: {e}")

        return endpoints

    def _extract_spring_endpoints(self, source_code: str, file_path: str, patterns: list) -> list[EndpointInfo]:
        """Extract Spring endpoints."""
        endpoints = []

        # Extract @RequestMapping(value = "/path")
        for pattern, _methods in patterns:
            for match in re.finditer(pattern, source_code, re.MULTILINE):
                try:
                    if "RequestMapping" in match.group(0):
                        value_match = re.search(r'value\s*=\s*["\']([^"\']+)["\']', match.group(0))
                        path = value_match.group(1) if value_match else "/"
                        http_methods = []

                        # Check for method in @RequestMapping
                        method_match = re.search(r"method\s*=\s*RequestMethod\.([^)]+)\)", match.group(0))
                        if method_match:
                            method = method_match.group(1)
                            if method == "GET":
                                http_methods = [HTTPMethod.GET]
                            elif method == "POST":
                                http_methods = [HTTPMethod.POST]
                            # TODO: add more methods
                        else:
                            http_methods = [HTTPMethod.GET, HTTPMethod.POST]  # Default

                        for method in http_methods:
                            endpoints.append(
                                EndpointInfo(
                                    http_method=method,
                                    path=path,
                                    name=None,
                                    parameters=[],
                                    return_type=None,
                                    middleware=[],
                                    entry_type=EntryPointType.API_ENDPOINT,
                                    framework="Spring",
                                    file_path=file_path,
                                    line_start=match.start() + 1,
                                )
                            )
                except Exception as e:
                    logger.warning(f"Failed to parse Spring endpoint: {e}")

        return endpoints

    def _extract_heuristic_endpoints(self, ast_tree: ASTTree, file_path: str) -> list[EndpointInfo]:
        """Extract entry points using heuristics when no framework is detected."""
        endpoints = []

        # Find main() function
        for func in ast_tree.all_functions():
            if func.name == "main":
                endpoints.append(
                    EndpointInfo(
                        http_method=None,
                        path="main",
                        name="main",
                        parameters=[],
                        return_type=None,
                        middleware=[],
                        entry_type=EntryPointType.MAIN_FUNCTION,
                        framework=None,
                        file_path=file_path,
                        line_start=func.line_start,
                    )
                )

        # Find public functions (no internal callers heuristic)
        public_funcs = self._find_public_functions(ast_tree)
        for func_info in public_funcs:
            endpoints.append(
                EndpointInfo(
                    http_method=None,
                    path=func_info["name"],
                    name=func_info["name"],
                    parameters=[],
                    return_type=func_info.get("return_type"),
                    middleware=[],
                    entry_type=EntryPointType.PUBLIC_FUNCTION,
                    framework=None,
                    file_path=file_path,
                    line_start=func_info["line_start"],
                )
            )

        return endpoints

    def _find_main_functions(self, ast_tree: ASTTree) -> list[dict]:
        """Find all main() functions."""
        main_functions = []

        for func in ast_tree.all_functions():
            if func.name == "main":
                main_functions.append(
                    {
                        "name": "main",
                        "line_start": func.line_start,
                        "line_end": func.line_end,
                        "parameters": [{"name": p.name, "type": p.type} for p in func.parameters],
                        "docstring": func.docstring,
                    }
                )

        return main_functions

    def _find_public_functions(self, ast_tree: ASTTree) -> list[dict]:
        """Find public functions using heuristic (no internal callers)."""
        # Simplified heuristic: functions not called by other functions in the same file
        called_function_names = set()
        for _func in ast_tree.all_functions():
            # TODO: analyze function calls to find called functions
            pass

        public_functions = []
        for func in ast_tree.all_functions():
            if func.name not in called_function_names and not func.name.startswith("_"):
                public_functions.append(
                    {
                        "name": func.name,
                        "line_start": func.line_start,
                        "line_end": func.line_end,
                        "parameters": [{"name": p.name, "type": p.type} for p in func.parameters],
                        "return_type": func.return_type,
                        "docstring": func.docstring,
                    }
                )

        return public_functions

    def analyze_project(
        self,
        source_files: list[dict],  # {file_path, content, language}
        project_id: int,
    ) -> EntryPointCatalog:
        """Analyze multiple source files and create unified catalog."""
        unified_catalog = EntryPointCatalog(language="multi")

        for file_info in source_files:
            try:
                file_catalog = self.analyze_file(
                    source_code=file_info["content"],
                    file_path=file_info["file_path"],
                    language=file_info["language"],
                )
                unified_catalog.source_files.extend(file_catalog.source_files)
                unified_catalog.endpoints.extend(file_catalog.endpoints)
                unified_catalog.main_functions.extend(file_catalog.main_functions)
                unified_catalog.public_functions.extend(file_catalog.public_functions)
                if file_catalog.framework_detected:
                    unified_catalog.framework_detected = True
            except Exception as e:
                logger.error(f"Failed to analyze {file_info.get('file_path')}: {e}")

        # Save to database
        self._save_to_database(unified_catalog, project_id)

        return unified_catalog

    def _save_to_database(self, catalog: EntryPointCatalog, project_id: int):
        """Save analysis results to database."""
        with get_sync_session() as db:
            result = AnalysisResult(
                project_id=project_id,
                analysis_type="entry_points",
                status=AnalysisStatus.COMPLETED,
                result_data=catalog.to_dict(),
            )
            db.add(result)
            db.commit()


def get_entry_points_analyzer() -> EntryPointsAnalyzer:
    """Get or create entry points analyzer instance."""
    return EntryPointsAnalyzer()
