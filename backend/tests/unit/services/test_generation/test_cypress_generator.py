"""Unit tests for the Cypress code generator — Epic 3, Story 3.12.

Covers AC1 (file structure + commands), AC2 (selector priority),
AC3 (visual snapshot), AC4 (kebab-case file path) and the cy.intercept
API-mock mapping. All exercises are pure-Python.
"""

from app.services.test_generation.codegen import CodeGenConfig, CodeGenRegistry
from app.services.test_generation.codegen.cypress_generator import CypressCodeGenerator


def _gen() -> CypressCodeGenerator:
    return CypressCodeGenerator(CodeGenConfig(validate_compilation=True))


class TestFactoryRegistration:
    def test_registry_returns_cypress_generator(self):
        gen = CodeGenRegistry.get_instance().get_generator("cypress")
        assert isinstance(gen, CypressCodeGenerator)
        assert gen.FRAMEWORK == "cypress"
        assert gen.LANGUAGE == "typescript"
        assert gen.FILE_EXTENSION == ".cy.ts"


class TestSelectorPriority:
    def test_data_cy_wins(self):
        gen = _gen()
        component = {"attributes": {"data-cy": "submit", "data-testid": "s", "role": "button"}}
        assert gen._resolve_selector(component) == '[data-cy="submit"]'

    def test_data_testid_second(self):
        gen = _gen()
        component = {"attributes": {"data-testid": "login", "role": "button"}}
        assert gen._resolve_selector(component) == '[data-testid="login"]'

    def test_role_third(self):
        gen = _gen()
        component = {"attributes": {"role": "dialog"}}
        assert gen._resolve_selector(component) == '[role="dialog"]'

    def test_text_fallback_returns_none(self):
        gen = _gen()
        component = {"attributes": {}, "label": "Zaloguj"}
        assert gen._resolve_selector(component) is None

    def test_cy_target_uses_contains_when_no_attrs(self):
        gen = _gen()
        step = {"component": {"label": "Zaloguj"}}
        assert gen._cy_target(step) == "cy.contains('Zaloguj')"


class TestStepMapping:
    def test_click(self):
        gen = _gen()
        cmds = gen._map_step_to_command({"action": "click", "selector": "#btn"})
        assert cmds == ["cy.get('#btn').click();"]

    def test_type(self):
        gen = _gen()
        cmds = gen._map_step_to_command(
            {"action": "type", "component": {"attributes": {"data-cy": "email"}}, "value": "a@b.pl"}
        )
        assert cmds == ["cy.get('[data-cy=\"email\"]').type('a@b.pl');"]

    def test_select(self):
        gen = _gen()
        cmds = gen._map_step_to_command({"action": "select", "selector": "#country", "value": "PL"})
        assert cmds == ["cy.get('#country').select('PL');"]

    def test_navigate(self):
        gen = _gen()
        cmds = gen._map_step_to_command({"action": "navigate", "url": "/login"})
        assert cmds == ["cy.visit('/login');"]

    def test_assert_text(self):
        gen = _gen()
        cmds = gen._map_step_to_command({"action": "assert_text", "selector": "h1", "value": "Witaj"})
        assert cmds == ["cy.get('h1').should('have.text', 'Witaj');"]

    def test_wait_api_emits_intercept_and_wait(self):
        gen = _gen()
        cmds = gen._map_step_to_command(
            {"action": "wait_api", "method": "post", "url": "/api/login", "alias": "login"}
        )
        assert cmds == [
            "cy.intercept('POST', '/api/login').as('login');",
            "cy.wait('@login');",
        ]

    def test_unknown_action_is_comment(self):
        gen = _gen()
        cmds = gen._map_step_to_command({"action": "frobnicate"})
        assert cmds[0].startswith("// nieobslugiwana akcja")


class TestVisualTesting:
    def test_snapshot_command(self):
        gen = _gen()
        cmd = gen._add_visual_testing_step({"title": "Strona logowania"})
        assert cmd.startswith("cy.matchImageSnapshot('strona-logowania'")
        assert "failureThreshold" in cmd
        assert "customDiffConfig" in cmd

    def test_visual_type_detected(self):
        gen = _gen()
        assert gen._is_visual({"type": "visual_regression"}) is True
        assert gen._is_visual({"visual": True}) is True
        assert gen._is_visual({"type": "e2e"}) is False


class TestGenerateTestFile:
    def test_basic_structure(self):
        gen = _gen()
        tc = {
            "title": "Logowanie uzytkownika",
            "type": "e2e",
            "steps": [
                {"action": "navigate", "url": "/login"},
                {"action": "type", "component": {"attributes": {"data-cy": "email"}}, "value": "a@b.pl"},
                {"action": "click", "component": {"attributes": {"data-testid": "submit"}}},
                {"action": "assert_visible", "component": {"label": "Pulpit"}},
            ],
        }
        result = gen.generate_test_file([tc])
        assert "describe('Logowanie uzytkownika'" in result.content
        assert "it('Logowanie uzytkownika'" in result.content
        assert "cy.visit('/login');" in result.content
        assert "cy.get('[data-cy=\"email\"]').type('a@b.pl');" in result.content
        assert "cy.contains('Pulpit').should('be.visible');" in result.content
        assert result.file_path == "cypress/e2e/logowanie-uzytkownika.cy.ts"
        assert result.compilation_result is not None
        assert result.compilation_result.success is True

    def test_base_url_in_before_each(self):
        gen = CypressCodeGenerator(CodeGenConfig(project_context={"base_url": "https://app.test"}))
        tc = {"title": "T", "type": "e2e", "steps": [{"action": "click", "selector": "#x"}]}
        result = gen.generate_test_file([tc])
        assert "beforeEach(() => {" in result.content
        assert "cy.visit('https://app.test');" in result.content

    def test_visual_test_adds_snapshot_and_import(self):
        gen = _gen()
        tc = {"title": "Pulpit", "type": "visual_regression", "steps": [{"action": "navigate", "url": "/"}]}
        result = gen.generate_test_file([tc])
        assert "cy.matchImageSnapshot('pulpit'" in result.content
        assert "import 'cypress-image-snapshot/command';" in result.content

    def test_empty_returns_placeholder(self):
        gen = _gen()
        result = gen.generate_test_file([])
        assert result.module_name == "empty"


class TestValidateSyntax:
    def test_valid_code(self):
        gen = _gen()
        code = "describe('x', () => { it('y', () => { cy.visit('/'); }); });\n"
        assert gen.validate_syntax(code).success is True

    def test_unbalanced_braces(self):
        gen = _gen()
        result = gen.validate_syntax("describe('x', () => { it('y', () => {")
        assert result.success is False

    def test_missing_describe(self):
        gen = _gen()
        result = gen.validate_syntax("const x = 1;")
        assert result.success is False
