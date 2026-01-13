"""
Base evaluator interface for MIT quality assessment.

Defines the abstract interface that all MIT evaluators must implement.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from avaliador.models.schemas import (
    EvaluationResult,
    ExtractionResult,
    MITType,
)


class BaseEvaluator(ABC):
    """
    Abstract base class for MIT evaluators.

    All MIT-specific evaluators should inherit from this class
    and implement the evaluate method.
    """

    # MIT type this evaluator handles
    mit_type: MITType

    # Minimum score for approval
    min_passing_score: float = 8.0

    @abstractmethod
    def evaluate(
        self,
        extraction: ExtractionResult | dict,
        include_metadata: bool = False,
    ) -> EvaluationResult:
        """
        Evaluate a document extraction.

        Args:
            extraction: Extraction result from DoclingExtractor.
            include_metadata: Whether to include detailed metadata.

        Returns:
            EvaluationResult with score and recommendations.
        """
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Get the system prompt for LLM evaluation.

        Returns:
            System prompt string.
        """
        pass

    @abstractmethod
    def get_user_prompt(self, extraction: ExtractionResult | dict) -> str:
        """
        Build user prompt with document content.

        Args:
            extraction: Extraction result.

        Returns:
            User prompt string with document content.
        """
        pass

    def validate_extraction(self, extraction: ExtractionResult | dict) -> bool:
        """
        Validate that extraction is suitable for evaluation.

        Args:
            extraction: Extraction result.

        Returns:
            True if extraction is valid.
        """
        if isinstance(extraction, dict):
            return bool(extraction.get("markdown"))
        return bool(extraction.markdown)

    def is_approved(self, result: EvaluationResult) -> bool:
        """
        Check if evaluation result meets approval threshold.

        Args:
            result: Evaluation result.

        Returns:
            True if score meets minimum passing score.
        """
        return result.score >= self.min_passing_score
