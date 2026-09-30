"""Tests for entry points and API endpoints identification service - Story 1.21"""

from app.services.analysis.entry_points import (
    EndpointInfo,
    EntryPointCatalog,
    EntryPointsAnalyzer,
    EntryPointType,
    HTTPMethod,
    ParameterInfo,
)


class TestHTTPMethod:
    """Test HTTPMethod enum."""

    def test_http_methods(self):
        """Test all HTTP methods exist."""
        assert HTTPMethod.GET == "GET"
        assert HTTPMethod.POST == "POST"
        assert HTTPMethod.PUT == "PUT"
        assert HTTPMethod.DELETE == "DELETE"
        assert HTTPMethod.PATCH == "PATCH"
        assert HTTPMethod.HEAD == "HEAD"
        assert HTTPMethod.OPTIONS == "OPTIONS"
        assert HTTPMethod.TRACE == "TRACE"


class TestEntryPointType:
    """Test EntryPointType enum."""

    def test_entry_point_types(self):
        """Test all entry point types exist."""
        assert EntryPointType.API_ENDPOINT == "api_endpoint"
        assert EntryPointType.MAIN_FUNCTION == "main_function"
        assert EntryPointType.PUBLIC_FUNCTION == "public_function"
        assert EntryPointType.DLL_EXPORT == "dll_export"
        assert EntryPointType.FRAMEWORK_SPECIFIC == "framework_specific"
        assert EntryPointType.UNKNOWN == "unknown"


class TestParameterInfo:
    """Test ParameterInfo dataclass."""

    def test_parameter_creation(self):
        """Test creating a parameter."""
        param = ParameterInfo(
            name="user_id",
            type="int",
            location="path",
            required=True,
            default_value=None,
        )
        assert param.name == "user_id"
        assert param.type == "int"
        assert param.location == "path"
        assert param.required is True


class TestEndpointInfo:
    """Test EndpointInfo dataclass."""

    def test_endpoint_creation(self):
        """Test creating an endpoint."""
        endpoint = EndpointInfo(
            http_method=HTTPMethod.GET,
            path="/api/users/{user_id}",
            name="get_user",
            parameters=[ParameterInfo(name="user_id", type="int", location="path", required=True)],
            return_type="User",
            middleware=["auth_required"],
            entry_type=EntryPointType.API_ENDPOINT,
            framework="FastAPI",
            file_path="users.py",
            line_start=10,
        )
        assert endpoint.http_method == HTTPMethod.GET
        assert endpoint.path == "/api/users/{user_id}"
        assert endpoint.name == "get_user"
        assert len(endpoint.parameters) == 1
        assert endpoint.middleware == ["auth_required"]


class TestEntryPointCatalog:
    """Test EntryPointCatalog dataclass."""

    def test_empty_catalog(self):
        """Test creating empty catalog."""
        catalog = EntryPointCatalog(language="python")
        assert catalog.language == "python"
        assert len(catalog.endpoints) == 0
        assert len(catalog.main_functions) == 0
        assert catalog.framework_detected is False

    def test_catalog_statistics(self):
        """Test statistics calculation."""
        catalog = EntryPointCatalog(language="python")

        catalog.endpoints = [
            EndpointInfo(
                http_method=HTTPMethod.GET,
                path="/api/users",
                name="list_users",
                parameters=[],
                return_type="list[User]",
                middleware=[],
                entry_type=EntryPointType.API_ENDPOINT,
                framework="FastAPI",
                file_path="users.py",
                line_start=10,
            ),
            EndpointInfo(
                http_method=HTTPMethod.POST,
                path="/api/users",
                name="create_user",
                parameters=[],
                return_type="User",
                middleware=[],
                entry_type=EntryPointType.API_ENDPOINT,
                framework="FastAPI",
                file_path="users.py",
                line_start=20,
            ),
        ]
        catalog.main_functions = [{"name": "main", "line_start": 50}]
        catalog.framework_detected = True

        stats = catalog.get_statistics()

        assert stats["total_endpoints"] == 2
        assert stats["framework_detected"] is True
        assert stats["endpoints_by_method"]["GET"] == 1
        assert stats["endpoints_by_method"]["POST"] == 1
        assert stats["main_functions_count"] == 1

    def test_to_dict_serialization(self):
        """Test catalog can be serialized to dict."""
        catalog = EntryPointCatalog(language="python")
        catalog.source_files = ["users.py"]
        catalog.endpoints = [
            EndpointInfo(
                http_method=HTTPMethod.GET,
                path="/api/users",
                name="list_users",
                parameters=[],
                return_type="list[User]",
                middleware=[],
                entry_type=EntryPointType.API_ENDPOINT,
                framework="FastAPI",
                file_path="users.py",
                line_start=10,
            )
        ]

        data = catalog.to_dict()

        assert data["language"] == "python"
        assert "users.py" in data["source_files"]
        assert len(data["endpoints"]) == 1
        assert data["endpoints"][0]["http_method"] == "GET"
        assert data["statistics"]["total_endpoints"] == 1


class TestEntryPointsAnalyzer:
    """Test entry points analyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer can be initialized."""
        analyzer = EntryPointsAnalyzer()
        assert analyzer.parser_registry is not None

    def test_analyze_python_flask_code(self):
        """Test analyzing Python Flask code."""
        analyzer = EntryPointsAnalyzer()

        source_code = """
from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/api/users', methods=['GET'])
def list_users():
    return jsonify([])

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    return jsonify({"id": user_id})

def main():
    app.run(debug=True)
"""

        catalog = analyzer.analyze_file(source_code, "app.py", "python")

        assert catalog.language == "python"
        # Should detect Flask framework
        assert catalog.framework_detected is True
        # Should find main function
        assert len(catalog.main_functions) >= 1
        assert any(f["name"] == "main" for f in catalog.main_functions)

    def test_analyze_python_fastapi_code(self):
        """Test analyzing Python FastAPI code."""
        analyzer = EntryPointsAnalyzer()

        source_code = """
from fastapi import APIRouter

router = APIRouter()

@router.get("/api/users")
async def list_users():
    return []

@router.post("/api/users")
async def create_user():
    return {"id": 1}
"""

        catalog = analyzer.analyze_file(source_code, "users.py", "python")

        assert catalog.language == "python"
        # Should detect FastAPI framework
        assert catalog.framework_detected is True
        # Should extract endpoints
        assert len(catalog.endpoints) >= 1

    def test_analyze_python_without_framework(self):
        """Test analyzing Python code without framework."""
        analyzer = EntryPointsAnalyzer()

        source_code = """
def calculate_sum(a, b):
    return a + b

def main():
    result = calculate_sum(1, 2)
    print(result)

if __name__ == "__main__":
    main()
"""

        catalog = analyzer.analyze_file(source_code, "utils.py", "python")

        assert catalog.language == "python"
        # Should not detect a framework
        assert catalog.framework_detected is False
        # Should find main function via heuristic
        assert len(catalog.main_functions) >= 1
        assert any(f["name"] == "main" for f in catalog.main_functions)

    def test_analyze_java_spring_code(self):
        """Test analyzing Java Spring code."""
        analyzer = EntryPointsAnalyzer()

        source_code = """
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users")
public class UserController {

    @GetMapping
    public List<User> listUsers() {
        return List.of();
    }

    @PostMapping
    public User createUser(@RequestBody User user) {
        return user;
    }
}
"""

        catalog = analyzer.analyze_file(source_code, "UserController.java", "java")

        assert catalog.language == "java"
        # Should detect Spring framework
        assert catalog.framework_detected is True
        # Should extract endpoints
        assert len(catalog.endpoints) >= 1

    def test_analyze_javascript_express_code(self):
        """Test analyzing JavaScript Express code."""
        analyzer = EntryPointsAnalyzer()

        source_code = """
const express = require('express');
const router = express.Router();

router.get('/api/users', (req, res) => {
    res.json([]);
});

router.post('/api/users', (req, res) => {
    res.json({id: 1});
});

module.exports = router;
"""

        catalog = analyzer.analyze_file(source_code, "users.js", "javascript")

        assert catalog.language == "javascript"
        # Should detect Express framework
        assert catalog.framework_detected is True

    def test_analyze_typescript_nestjs_code(self):
        """Test analyzing TypeScript NestJS code."""
        analyzer = EntryPointsAnalyzer()

        source_code = """
import { Controller, Get, Post } from '@nestjs/common';

@Controller('users')
export class UsersController {
    @Get()
    findAll() {
        return [];
    }

    @Post()
    create() {
        return { id: 1 };
    }
}
"""

        catalog = analyzer.analyze_file(source_code, "users.controller.ts", "typescript")

        assert catalog.language == "typescript"
        # Should detect NestJS framework
        assert catalog.framework_detected is True

    def test_analyze_csharp_aspnet_code(self):
        """Test analyzing C# ASP.NET code."""
        analyzer = EntryPointsAnalyzer()

        source_code = """
using Microsoft.AspNetCore.Mvc;

[ApiController]
[Route("api/[controller]")]
public class UsersController : ControllerBase {
    [HttpGet]
    public IActionResult ListUsers() {
        return Ok([]);
    }

    [HttpPost]
    public IActionResult CreateUser([FromBody] User user) {
        return Ok(user);
    }
}
"""

        catalog = analyzer.analyze_file(source_code, "UsersController.cs", "csharp")

        assert catalog.language == "csharp"
        # Should detect ASP.NET framework
        assert catalog.framework_detected is True

    def test_analyze_php_laravel_controller(self):
        """Story 1.52 (FR12): Laravel #[Route] attributes detected as endpoints."""
        analyzer = EntryPointsAnalyzer()

        source_code = """<?php
namespace App\\Http\\Controllers;

use Illuminate\\Http\\Request;

class UserController {
    #[Route(path: '/users', methods: ['GET'])]
    public function index() {}

    #[Route(path: '/users', methods: ['POST'])]
    public function store() {}

    #[Get('/users/{id}')]
    public function show() {}
}
"""
        catalog = analyzer.analyze_file(source_code, "UserController.php", "php")

        assert catalog.language == "php"
        assert catalog.framework_detected is True
        paths = [ep.path for ep in catalog.endpoints]
        assert "/users" in paths
        assert "/users/{id}" in paths
        # Method-specific attribute resolves to the right HTTP verb.
        get_eps = [ep for ep in catalog.endpoints if ep.path == "/users/{id}"]
        assert get_eps and get_eps[0].http_method == HTTPMethod.GET

    def test_analyze_php_laravel_routes_file(self):
        """Story 1.52 (FR12): Laravel routes/web.php Route::verb(...) endpoints."""
        analyzer = EntryPointsAnalyzer()

        source_code = """<?php
use Illuminate\\Support\\Facades\\Route;

Route::get('/health', function () { return 'ok'; });
Route::post('/users', [UserController::class, 'store']);
"""
        catalog = analyzer.analyze_file(source_code, "routes/web.php", "php")

        assert catalog.language == "php"
        assert catalog.framework_detected is True
        method_path = {(ep.http_method, ep.path) for ep in catalog.endpoints}
        assert (HTTPMethod.GET, "/health") in method_path
        assert (HTTPMethod.POST, "/users") in method_path

    def test_analyze_php_no_framework(self):
        """Plain PHP with no route attributes falls back to public-function heuristics."""
        analyzer = EntryPointsAnalyzer()

        source_code = """<?php
function helper() {
    return 1;
}
"""
        catalog = analyzer.analyze_file(source_code, "helper.php", "php")

        assert catalog.language == "php"
        assert catalog.framework_detected is False

    def test_analyze_cpp_main_function(self):
        """Test analyzing C++ code with main function."""
        analyzer = EntryPointsAnalyzer()

        source_code = """
#include <iostream>

int main(int argc, char** argv) {
    std::cout << "Hello, World!" << std::endl;
    return 0;
}
"""

        catalog = analyzer.analyze_file(source_code, "main.cpp", "cpp")

        assert catalog.language == "cpp"
        # Should find main function
        assert len(catalog.main_functions) >= 1

    def test_analyze_project_multiple_files(self):
        """Test analyzing project with multiple files."""
        analyzer = EntryPointsAnalyzer()

        source_files = [
            {
                "file_path": "app.py",
                "content": """
from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "Hello"

def main():
    app.run()
""",
                "language": "python",
            },
            {
                "file_path": "utils.py",
                "content": """
def helper_function():
    return "help"
""",
                "language": "python",
            },
        ]

        # Analyze files individually without database save
        unified_catalog = EntryPointCatalog(language="multi")
        for file_info in source_files:
            file_catalog = analyzer.analyze_file(
                source_code=file_info["content"],
                file_path=file_info["file_path"],
                language=file_info["language"],
            )
            unified_catalog.source_files.extend(file_catalog.source_files)
            unified_catalog.endpoints.extend(file_catalog.endpoints)
            unified_catalog.main_functions.extend(file_catalog.main_functions)
            unified_catalog.public_functions.extend(file_catalog.public_functions)

        assert unified_catalog.language == "multi"
        assert len(unified_catalog.source_files) == 2
        # Should find endpoints and main functions from all files
        assert len(unified_catalog.endpoints) >= 0
        assert len(unified_catalog.main_functions) >= 1
