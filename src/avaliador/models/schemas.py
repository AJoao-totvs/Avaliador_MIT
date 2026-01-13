"""
Pydantic schemas for Avaliador de MITs.

Defines data models for evaluation results, extraction results, and metadata.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MITType(str, Enum):
    """Supported MIT document types."""

    MIT041 = "MIT041"  # Desenho da Solucao / Blueprint
    MIT043 = "MIT043"  # Especificacao Tecnica
    MIT037 = "MIT037"  # Roteiro de Treinamento
    MIT045 = "MIT045"  # Roteiro de Testes
    MIT065 = "MIT065"  # Termo de Encerramento


class DiagramDescription(BaseModel):
    """Description of a diagram extracted from the document."""

    index: int = Field(..., description="Index of the diagram in the document")
    description: str = Field(..., description="Text description of the diagram content")
    diagram_type: Optional[str] = Field(
        default=None, description="Type of diagram (BPMN, flowchart, etc.)"
    )


class ExtractionMetadata(BaseModel):
    """Metadata about the document extraction process."""

    word_count: int = Field(..., description="Total word count of the document")
    image_count: int = Field(..., description="Total number of images in the document")
    relevant_images: int = Field(..., description="Number of relevant images (diagrams) processed")
    vision_enabled: bool = Field(..., description="Whether vision analysis was enabled")
    extraction_timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of the extraction",
    )


class ExtractionResult(BaseModel):
    """Result of document extraction."""

    markdown: str = Field(..., description="Full document content in Markdown format")
    diagrams: list[DiagramDescription] = Field(
        default_factory=list, description="List of diagram descriptions"
    )
    metadata: ExtractionMetadata = Field(..., description="Extraction metadata")

    @property
    def has_diagrams(self) -> bool:
        """Check if the extraction contains any diagram descriptions."""
        return len(self.diagrams) > 0


class PillarScore(BaseModel):
    """Score for a single evaluation pillar."""

    pillar_id: str = Field(..., description="Unique identifier for the pillar")
    pillar_name: str = Field(..., description="Human-readable name of the pillar")
    weight: float = Field(..., ge=0, le=1, description="Weight of this pillar (0-1)")
    score: float = Field(..., ge=0, le=10, description="Score for this pillar (0-10)")
    max_score: float = Field(default=10.0, description="Maximum possible score")


class EvaluationMetadata(BaseModel):
    """Metadata about the evaluation process."""

    mit_type: MITType = Field(..., description="Type of MIT document evaluated")
    document_name: str = Field(..., description="Name of the evaluated document")
    word_count: int = Field(..., description="Word count of the document")
    image_count: int = Field(..., description="Number of images in the document")
    relevant_images: int = Field(..., description="Number of relevant diagrams")
    vision_enabled: bool = Field(..., description="Whether vision was used")
    cached: bool = Field(default=False, description="Whether extraction was cached")
    evaluation_timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of the evaluation",
    )
    pillar_scores: Optional[list[PillarScore]] = Field(
        default=None, description="Detailed scores per pillar"
    )


class EvaluationResult(BaseModel):
    """
    Result of MIT quality evaluation.

    This is the primary output format of the CLI tool.
    """

    score: float = Field(
        ...,
        ge=0,
        le=10,
        description="Overall quality score from 0.0 to 10.0",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="List of actionable recommendations. Empty if score is 10.0",
    )
    metadata: Optional[EvaluationMetadata] = Field(
        default=None,
        description="Optional metadata for debugging and frontend integration",
    )

    @property
    def is_approved(self) -> bool:
        """Check if the document meets minimum quality threshold (8.0)."""
        return self.score >= 8.0

    @property
    def verdict(self) -> str:
        """Get human-readable verdict based on score."""
        if self.score >= 9.0:
            return "EXCELENTE"
        elif self.score >= 8.0:
            return "APROVADO"
        elif self.score >= 5.0:
            return "REQUER REVISAO"
        else:
            return "REPROVADO"

    def to_simple_dict(self) -> dict:
        """Return simplified dict with only score and recommendations."""
        return {
            "score": self.score,
            "recommendations": self.recommendations,
        }
