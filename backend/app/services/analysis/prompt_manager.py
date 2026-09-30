"""
Central prompt repository manager with versioning and A/B testing.

Features:
- Load prompts from YAML files
- Version management (v1, v2, etc.)
- Jinja2 template rendering
- A/B testing support
- Prompt validation
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import jinja2
import yaml

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PromptVersion(StrEnum):
    """Special prompt version selectors."""
    LATEST = "latest"
    STABLE = "stable"


@dataclass
class PromptVariable:
    """Variable definition in prompt template."""
    name: str
    type: str
    required: bool
    default: str | None = None


@dataclass
class Prompt:
    """Loaded prompt with metadata."""
    name: str
    version: str
    description: str
    model: str
    max_tokens: int
    temperature: float
    template: jinja2.Template
    variables: list[PromptVariable]
    ab_test_percentage: int = 0
    content_hash: str = ""

    def render(self, **kwargs) -> str:
        """Render prompt template with given variables."""
        # Validate required variables
        provided = set(kwargs.keys())
        required = {v.name for v in self.variables if v.required}
        missing = required - provided
        if missing:
            raise ValueError(f"Missing required prompt variables: {missing}")

        # Set defaults for missing optional variables
        for var in self.variables:
            if var.name not in kwargs and var.default is not None:
                kwargs[var.name] = var.default

        return self.template.render(**kwargs)


class PromptManager:
    """Central prompt repository manager."""

    def __init__(self, prompts_dir: Path | None = None):
        self.prompts_dir = prompts_dir or settings.prompts_dir
        self._cache: dict[str, dict[str, Prompt]] = {}  # name -> version -> Prompt
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.prompts_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._load_all_prompts()

    def _load_all_prompts(self):
        """Load all prompts from the prompts directory."""
        if not self.prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {self.prompts_dir}")
            return

        for prompt_file in self.prompts_dir.glob("*.yaml"):
            try:
                self._load_prompt_file(prompt_file)
            except Exception as e:
                logger.error(f"Failed to load prompt from {prompt_file}: {e}")

        logger.info(f"Loaded {sum(len(v) for v in self._cache.values())} prompt versions")

    def _load_prompt_file(self, file_path: Path):
        """Load a single prompt YAML file."""
        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        name = data["name"]
        version = data["version"]

        # Parse variables
        variables = []
        for var_data in data.get("variables", []):
            variables.append(
                PromptVariable(
                    name=var_data["name"],
                    type=var_data["type"],
                    required=var_data.get("required", False),
                    default=var_data.get("default"),
                )
            )

        # Create template
        template_str = data["template"]
        template = self._jinja_env.from_string(template_str)
        content_hash = hashlib.sha256(template_str.encode()).hexdigest()[:16]

        prompt = Prompt(
            name=name,
            version=version,
            description=data.get("description", ""),
            model=data.get("model", "claude-sonnet-4-20250514"),
            max_tokens=data.get("max_tokens", 4096),
            temperature=data.get("temperature", 0.7),
            template=template,
            variables=variables,
            ab_test_percentage=data.get("ab_test_percentage", 0),
            content_hash=content_hash,
        )

        if name not in self._cache:
            self._cache[name] = {}
        self._cache[name][version] = prompt
        logger.debug(f"Loaded prompt: {name} version {version}")

    def get(
        self,
        name: str,
        version: str | None = None,
        tenant_id: int | None = None,
    ) -> Prompt:
        """
        Get a prompt by name and version.

        Args:
            name: Prompt name (e.g., "code_analysis.extract_functions")
            version: Prompt version (v1, v2, "latest", "stable"). Defaults to "stable"
            tenant_id: Tenant ID for A/B testing

        Returns:
            Prompt object with rendered template available

        Raises:
            ValueError: If prompt or version not found
        """
        if name not in self._cache:
            raise ValueError(f"Prompt not found: {name}")

        available_versions = self._cache[name]

        # Determine version to use
        if version is None or version == PromptVersion.STABLE:
            # Use v1 as stable default
            version = "v1"
        elif version == PromptVersion.LATEST:
            # Use highest version number
            version = max(available_versions.keys(), key=lambda v: int(v[1:]))

        # A/B testing logic
        if tenant_id is not None:
            prompt = self._get_for_ab_test(name, available_versions, tenant_id)
            if prompt:
                logger.debug(f"AB-test: using version {prompt.version} for tenant {tenant_id}")
                return prompt

        if version not in available_versions:
            available = ", ".join(available_versions.keys())
            raise ValueError(
                f"Prompt version {version} not found for {name}. Available: {available}"
            )

        return available_versions[version]

    def _get_for_ab_test(
        self,
        name: str,
        versions: dict[str, Prompt],
        tenant_id: int,
    ) -> Prompt | None:
        """Select prompt version for A/B testing based on tenant_id hash."""
        import random

        # Simple hash-based selection for consistent assignment
        hash_val = int(hashlib.sha256(f"{name}:{tenant_id}".encode()).hexdigest(), 16)
        hash_percent = hash_val % 100

        for version, prompt in versions.items():
            if prompt.ab_test_percentage > 0 and hash_percent < prompt.ab_test_percentage:
                return prompt

        return None

    def list_prompts(self) -> dict[str, list[str]]:
        """List all available prompts and their versions."""
        return {
            name: list(versions.keys())
            for name, versions in sorted(self._cache.items())
        }

    def get_prompt_info(self, name: str) -> dict:
        """Get information about all versions of a prompt."""
        if name not in self._cache:
            raise ValueError(f"Prompt not found: {name}")

        info = {"name": name, "versions": []}
        for version, prompt in self._cache[name].items():
            info["versions"].append(
                {
                    "version": version,
                    "description": prompt.description,
                    "model": prompt.model,
                    "max_tokens": prompt.max_tokens,
                    "temperature": prompt.temperature,
                    "ab_test_percentage": prompt.ab_test_percentage,
                    "hash": prompt.content_hash,
                }
            )

        return info

    def reload(self):
        """Reload all prompts from disk."""
        self._cache.clear()
        self._load_all_prompts()


# Global prompt manager instance
_manager: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    """Get or create global prompt manager instance."""
    global _manager
    if _manager is None:
        _manager = PromptManager()
    return _manager
