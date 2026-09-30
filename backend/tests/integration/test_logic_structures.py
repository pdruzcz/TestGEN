"""Tests for logic structures identification service - Story 1.20"""

from app.services.analysis.logic_structures import (
    CodeStructureCatalog,
    FunctionInfo,
    LogicStructuresAnalyzer,
    VisibilityLevel,
)


class TestCodeStructureCatalog:
    """Test CodeStructureCatalog data class."""

    def test_empty_catalog(self):
        """Test creating empty catalog."""
        catalog = CodeStructureCatalog(language="python")
        assert catalog.language == "python"
        assert len(catalog.functions) == 0
        assert len(catalog.classes) == 0
        assert catalog.total_loc == 0

    def test_catalog_statistics(self):
        """Test statistics calculation."""
        catalog = CodeStructureCatalog(language="python")

        # Add some test data
        catalog.functions = [
            FunctionInfo(
                name="simple_func",
                parameters=[],
                return_type="None",
                visibility=VisibilityLevel.PUBLIC,
                complexity=2,
                loc=5,
                line_start=10,
                line_end=15,
                docstring=None,
                file_path="test.py",
            ),
            FunctionInfo(
                name="complex_func",
                parameters=[],
                return_type="str",
                visibility=VisibilityLevel.PRIVATE,
                complexity=15,
                loc=20,
                line_start=20,
                line_end=40,
                docstring=None,
                file_path="test.py",
            ),
        ]
        catalog.total_functions = 2
        catalog.total_loc = 25

        stats = catalog.get_statistics()

        assert stats["total_functions"] == 2
        assert stats["average_complexity"] == 8.5  # (2 + 15) / 2
        assert stats["complexity_levels"]["low"] == 1
        assert stats["complexity_levels"]["medium"] == 0
        assert stats["complexity_levels"]["high"] == 1
        assert stats["visibility_distribution"]["public"] == 1
        assert stats["visibility_distribution"]["private"] == 1

    def test_filter_by_complexity(self):
        """Test filtering catalog by complexity level."""
        catalog = CodeStructureCatalog(language="python")
        catalog.functions = [
            FunctionInfo(
                name="low_complexity",
                parameters=[],
                return_type="None",
                visibility=VisibilityLevel.PUBLIC,
                complexity=3,
                loc=5,
                line_start=1,
                line_end=5,
                docstring=None,
                file_path="test.py",
            ),
            FunctionInfo(
                name="high_complexity",
                parameters=[],
                return_type="str",
                visibility=VisibilityLevel.PUBLIC,
                complexity=12,
                loc=20,
                line_start=10,
                line_end=30,
                docstring=None,
                file_path="test.py",
            ),
        ]
        catalog.total_functions = 2

        # Filter to low complexity only
        filtered = catalog.filter_by_complexity("low")
        assert len(filtered.functions) == 1
        assert filtered.functions[0].name == "low_complexity"

        # Filter to medium or lower
        filtered = catalog.filter_by_complexity("medium")
        assert len(filtered.functions) == 1  # only low_complexity (3 <= medium threshold)

    def test_filter_by_visibility(self):
        """Test filtering catalog by visibility."""
        catalog = CodeStructureCatalog(language="python")
        catalog.functions = [
            FunctionInfo(
                name="public_func",
                parameters=[],
                return_type="None",
                visibility=VisibilityLevel.PUBLIC,
                complexity=1,
                loc=5,
                line_start=1,
                line_end=5,
                docstring=None,
                file_path="test.py",
            ),
            FunctionInfo(
                name="private_func",
                parameters=[],
                return_type="str",
                visibility=VisibilityLevel.PRIVATE,
                complexity=1,
                loc=5,
                line_start=10,
                line_end=15,
                docstring=None,
                file_path="test.py",
            ),
        ]
        catalog.total_functions = 2

        filtered = catalog.filter_by_visibility(VisibilityLevel.PUBLIC)
        assert len(filtered.functions) == 1
        assert filtered.functions[0].name == "public_func"


class TestLogicStructuresAnalyzer:
    """Test logic structures analyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer can be initialized."""
        analyzer = LogicStructuresAnalyzer()
        assert analyzer.parser_registry is not None

    def test_analyze_simple_python_code(self):
        """Test analyzing simple Python code."""
        analyzer = LogicStructuresAnalyzer()

        source_code = """
def hello_world():
    '''A simple greeting function.'''
    print("Hello, World!")

class MyClass:
    def method1(self):
        pass
"""

        catalog = analyzer.analyze_file(source_code, "test.py", "python")

        assert catalog.language == "python"
        assert len(catalog.functions) == 1  # hello_world only (class methods counted separately)
        assert len(catalog.classes) == 1
        assert catalog.classes[0].name == "MyClass"
        assert len(catalog.classes[0].methods) == 1

    def test_analyze_python_with_complexity(self):
        """Test complexity calculation for Python code."""
        analyzer = LogicStructuresAnalyzer()

        source_code = """
def complex_function(x):
    if x > 0:
        for i in range(10):
            if i % 2 == 0:
                return i
    return x
"""

        catalog = analyzer.analyze_file(source_code, "test.py", "python")

        # Should find the function and calculate complexity
        assert len(catalog.functions) >= 1
        # The function should have complexity > 1 due to nested if/for
        func = next((f for f in catalog.functions if f.name == "complex_function"), None)
        assert func is not None
        assert func.complexity > 1

    def test_visibility_detection(self):
        """Test visibility detection for Python functions."""
        analyzer = LogicStructuresAnalyzer()

        source_code = """
def public_func():
    pass

def _private_func():
    pass

def __internal_func__():
    pass
"""

        catalog = analyzer.analyze_file(source_code, "test.py", "python")

        public_funcs = [f for f in catalog.functions if f.visibility == VisibilityLevel.PUBLIC]
        private_funcs = [f for f in catalog.functions if f.visibility == VisibilityLevel.PRIVATE]
        internal_funcs = [f for f in catalog.functions if f.visibility == VisibilityLevel.INTERNAL]

        assert len(public_funcs) == 1
        assert len(private_funcs) == 2  # _private_func and __internal_func__ both detected as private
        assert len(internal_funcs) == 0

    def test_to_dict_serialization(self):
        """Test catalog can be serialized to dict."""
        catalog = CodeStructureCatalog(language="python")
        catalog.source_files = ["test.py"]
        catalog.total_functions = 1
        catalog.total_classes = 0
        catalog.total_loc = 10

        data = catalog.to_dict()

        assert data["language"] == "python"
        assert "test.py" in data["source_files"]
        assert data["total_functions"] == 1


class TestVisibilityLevel:
    """Test VisibilityLevel enum."""

    def test_visibility_levels(self):
        """Test all visibility levels exist."""
        assert VisibilityLevel.PUBLIC == "public"
        assert VisibilityLevel.PROTECTED == "protected"
        assert VisibilityLevel.PRIVATE == "private"
        assert VisibilityLevel.INTERNAL == "internal"
