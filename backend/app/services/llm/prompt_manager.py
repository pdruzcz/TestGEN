"""
Prompt Manager service wrapper.
Re-exports from app.services.analysis.prompt_manager for compatibility.
"""

from app.services.analysis.prompt_manager import (
    PromptManager,
    get_prompt_manager,
)

__all__ = [
    "PromptManager",
    "get_prompt_manager",
]
