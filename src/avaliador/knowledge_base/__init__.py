"""Knowledge base module for evaluation criteria and references."""

from avaliador.knowledge_base.loader import load_criteria, get_prompt
from avaliador.knowledge_base.references import (
    get_references,
    get_reference_prompt,
    ReferenceManager,
)

__all__ = [
    "load_criteria",
    "get_prompt",
    "get_references",
    "get_reference_prompt",
    "ReferenceManager",
]
