"""Unit tests for FrameworkDetector."""

import json
import os

import pytest

from app.services.project.framework_detector import FrameworkDetector


@pytest.fixture()
def detector():
    return FrameworkDetector()


def _write_file(directory: str, filename: str, content: str) -> str:
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestPythonFramework:
    def test_pytest_in_requirements(self, detector, tmp_path):
        _write_file(str(tmp_path), "requirements.txt", "pytest\nrequests\n")
        assert detector.detect_framework(str(tmp_path), "python") == "pytest"

    def test_pytest_in_pyproject(self, detector, tmp_path):
        _write_file(
            str(tmp_path),
            "pyproject.toml",
            '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
        )
        assert detector.detect_framework(str(tmp_path), "python") == "pytest"

    def test_unittest_fallback(self, detector, tmp_path):
        _write_file(str(tmp_path), "requirements.txt", "unittest\n")
        assert detector.detect_framework(str(tmp_path), "python") == "unittest"

    def test_nose2_detection(self, detector, tmp_path):
        _write_file(str(tmp_path), "requirements.txt", "nose2\n")
        assert detector.detect_framework(str(tmp_path), "python") == "nose2"

    def test_no_python_framework(self, detector, tmp_path):
        _write_file(str(tmp_path), "main.py", "print('hello')\n")
        assert detector.detect_framework(str(tmp_path), "python") is None


class TestJavaScriptFramework:
    def test_jest_in_package_json(self, detector, tmp_path):
        pkg = {"devDependencies": {"jest": "^29.0.0"}}
        _write_file(str(tmp_path), "package.json", json.dumps(pkg))
        assert detector.detect_framework(str(tmp_path), "javascript") == "jest"

    def test_mocha_in_package_json(self, detector, tmp_path):
        pkg = {"devDependencies": {"mocha": "^10.0.0"}}
        _write_file(str(tmp_path), "package.json", json.dumps(pkg))
        assert detector.detect_framework(str(tmp_path), "javascript") == "mocha"

    def test_vitest_in_package_json(self, detector, tmp_path):
        pkg = {"devDependencies": {"vitest": "^1.0.0"}}
        _write_file(str(tmp_path), "package.json", json.dumps(pkg))
        assert detector.detect_framework(str(tmp_path), "javascript") == "vitest"

    def test_typescript_uses_package_json(self, detector, tmp_path):
        pkg = {"devDependencies": {"jest": "^29.0.0"}}
        _write_file(str(tmp_path), "package.json", json.dumps(pkg))
        assert detector.detect_framework(str(tmp_path), "typescript") == "jest"

    def test_no_js_framework(self, detector, tmp_path):
        _write_file(str(tmp_path), "index.js", "console.log('hi')\n")
        assert detector.detect_framework(str(tmp_path), "javascript") is None


class TestJavaFramework:
    def test_junit5_in_pom(self, detector, tmp_path):
        pom = "<dependencies><dependency><groupId>org.junit.jupiter</groupId></dependency></dependencies>"
        _write_file(str(tmp_path), "pom.xml", pom)
        assert detector.detect_framework(str(tmp_path), "java") == "junit5"

    def test_junit4_in_pom(self, detector, tmp_path):
        pom = "<dependencies><dependency><groupId>junit</groupId></dependency></dependencies>"
        _write_file(str(tmp_path), "pom.xml", pom)
        assert detector.detect_framework(str(tmp_path), "java") == "junit4"

    def test_testng_in_pom(self, detector, tmp_path):
        pom = "<dependencies><dependency><groupId>org.testng</groupId></dependency></dependencies>"
        _write_file(str(tmp_path), "pom.xml", pom)
        assert detector.detect_framework(str(tmp_path), "java") == "testng"

    def test_junit5_in_gradle(self, detector, tmp_path):
        gradle = "dependencies { testImplementation 'org.junit.jupiter:junit-jupiter' }"
        _write_file(str(tmp_path), "build.gradle", gradle)
        assert detector.detect_framework(str(tmp_path), "java") == "junit5"

    def test_no_java_framework(self, detector, tmp_path):
        _write_file(str(tmp_path), "App.java", "class App {}\n")
        assert detector.detect_framework(str(tmp_path), "java") is None


class TestCSharpFramework:
    def test_xunit_in_csproj(self, detector, tmp_path):
        csproj = '<ItemGroup><PackageReference Include="xunit" Version="2.4" /></ItemGroup>'
        _write_file(str(tmp_path), "App.csproj", csproj)
        assert detector.detect_framework(str(tmp_path), "csharp") == "xunit"

    def test_nunit_in_csproj(self, detector, tmp_path):
        csproj = '<ItemGroup><PackageReference Include="NUnit" Version="3.13" /></ItemGroup>'
        _write_file(str(tmp_path), "App.csproj", csproj)
        assert detector.detect_framework(str(tmp_path), "csharp") == "nunit"

    def test_mstest_in_csproj(self, detector, tmp_path):
        csproj = '<ItemGroup><PackageReference Include="MSTest.TestFramework" Version="3.0" /></ItemGroup>'
        _write_file(str(tmp_path), "App.csproj", csproj)
        assert detector.detect_framework(str(tmp_path), "csharp") == "mstest"

    def test_no_csharp_framework(self, detector, tmp_path):
        _write_file(str(tmp_path), "Program.cs", "class Program {}\n")
        assert detector.detect_framework(str(tmp_path), "csharp") is None


class TestCppFramework:
    def test_gtest_in_cmake(self, detector, tmp_path):
        cmake = "find_package(GTest REQUIRED)\n"
        _write_file(str(tmp_path), "CMakeLists.txt", cmake)
        assert detector.detect_framework(str(tmp_path), "cpp") == "gtest"

    def test_catch2_in_cmake(self, detector, tmp_path):
        cmake = "find_package(Catch2 REQUIRED)\n"
        _write_file(str(tmp_path), "CMakeLists.txt", cmake)
        assert detector.detect_framework(str(tmp_path), "cpp") == "catch2"

    def test_no_cpp_framework(self, detector, tmp_path):
        _write_file(str(tmp_path), "main.cpp", "int main() {}\n")
        assert detector.detect_framework(str(tmp_path), "cpp") is None


class TestUnknownLanguage:
    def test_unknown_language_returns_none(self, detector, tmp_path):
        assert detector.detect_framework(str(tmp_path), "rust") is None


class TestPhpFramework:
    """Story 1.52 (FR12) — PHP test framework detection from composer.json."""

    def test_phpunit_in_composer_require(self, detector, tmp_path):
        pkg = {"require-dev": {"phpunit/phpunit": "^11.0"}}
        _write_file(str(tmp_path), "composer.json", json.dumps(pkg))
        assert detector.detect_framework(str(tmp_path), "php") == "phpunit"

    def test_pest_in_composer_require(self, detector, tmp_path):
        pkg = {"require-dev": {"pestphp/pest": "^2.0"}}
        _write_file(str(tmp_path), "composer.json", json.dumps(pkg))
        assert detector.detect_framework(str(tmp_path), "php") == "pest"

    def test_phpunit_in_require(self, detector, tmp_path):
        pkg = {"require": {"phpunit/phpunit": "^10.0"}}
        _write_file(str(tmp_path), "composer.json", json.dumps(pkg))
        assert detector.detect_framework(str(tmp_path), "php") == "phpunit"

    def test_pest_takes_priority(self, detector, tmp_path):
        """Pest is checked before phpunit (pest builds on phpunit but is the surface API)."""
        pkg = {"require-dev": {"phpunit/phpunit": "^11.0", "pestphp/pest": "^3.0"}}
        _write_file(str(tmp_path), "composer.json", json.dumps(pkg))
        assert detector.detect_framework(str(tmp_path), "php") == "pest"

    def test_no_composer_json(self, detector, tmp_path):
        _write_file(str(tmp_path), "index.php", "<?php echo 'hi';\n")
        assert detector.detect_framework(str(tmp_path), "php") is None

    def test_composer_without_test_framework(self, detector, tmp_path):
        pkg = {"require": {"laravel/framework": "^11.0"}}
        _write_file(str(tmp_path), "composer.json", json.dumps(pkg))
        assert detector.detect_framework(str(tmp_path), "php") is None

    def test_malformed_composer_json(self, detector, tmp_path):
        _write_file(str(tmp_path), "composer.json", "{not valid json")
        assert detector.detect_framework(str(tmp_path), "php") is None
