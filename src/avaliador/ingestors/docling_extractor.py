"""
Document extractor using Docling library.

Extracts text, structure, and images from DOCX files.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from avaliador.config import settings
from avaliador.ingestors.image_filter import ImageFilter
from avaliador.models.schemas import (
    DiagramDescription,
    ExtractionMetadata,
    ExtractionResult,
)


class DoclingExtractor:
    """
    Document extractor using Docling library.

    Supports DOCX extraction with optional VLM-based image description.
    """

    def __init__(
        self,
        enable_vision: bool = True,
        image_filter: Optional[ImageFilter] = None,
    ):
        """
        Initialize extractor.

        Args:
            enable_vision: Whether to use VLM for image description.
            image_filter: Custom image filter. Defaults to standard filter.
        """
        self.enable_vision = enable_vision and settings.vision_enabled
        self.image_filter = image_filter or ImageFilter()
        self._converter = None

    def _get_converter(self):
        """Lazy-load Docling converter."""
        if self._converter is None:
            try:
                from docling.datamodel.base_models import InputFormat
                from docling.datamodel.pipeline_options import (
                    PictureDescriptionApiOptions,
                )
                from docling.document_converter import (
                    DocumentConverter,
                    WordFormatOption,
                )

                # Configure pipeline options
                format_options = {
                    InputFormat.DOCX: WordFormatOption(),
                }

                # Add VLM configuration if vision is enabled
                if self.enable_vision and settings.dta_proxy_api_key:
                    # Note: VLM integration will be configured when Docling
                    # supports custom API endpoints
                    pass

                self._converter = DocumentConverter(format_options=format_options)

            except ImportError as e:
                raise ImportError(
                    "Docling is not installed. Install with: pip install docling"
                ) from e

        return self._converter

    def extract(self, file_path: Path) -> ExtractionResult:
        """
        Extract content from a document.

        Args:
            file_path: Path to the document file.

        Returns:
            ExtractionResult with markdown content and diagram descriptions.

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file format is not supported.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Validate file extension
        if file_path.suffix.lower() not in [".docx", ".doc"]:
            raise ValueError(
                f"Unsupported file format: {file_path.suffix}. Only .docx files are supported."
            )

        converter = self._get_converter()

        # Convert document
        result = converter.convert(str(file_path))
        doc = result.document

        # Export to markdown
        markdown = doc.export_to_markdown()

        # Count words
        word_count = len(markdown.split())

        # Get pictures and filter relevant ones
        all_pictures = list(doc.pictures) if hasattr(doc, "pictures") else []
        relevant_pictures = self.image_filter.filter_pictures(all_pictures)

        # Extract diagram descriptions
        diagrams: list[DiagramDescription] = []
        if self.enable_vision:
            for i, pic in enumerate(relevant_pictures):
                # Check for existing description from Docling
                description = ""
                if hasattr(pic, "meta") and pic.meta:
                    if hasattr(pic.meta, "description") and pic.meta.description:
                        description = (
                            pic.meta.description.text
                            if hasattr(pic.meta.description, "text")
                            else str(pic.meta.description)
                        )

                if description:
                    diagrams.append(
                        DiagramDescription(
                            index=i,
                            description=description,
                            diagram_type=self._detect_diagram_type(description),
                        )
                    )

        # Build metadata
        metadata = ExtractionMetadata(
            word_count=word_count,
            image_count=len(all_pictures),
            relevant_images=len(relevant_pictures),
            vision_enabled=self.enable_vision and len(diagrams) > 0,
            extraction_timestamp=datetime.now(),
        )

        return ExtractionResult(
            markdown=markdown,
            diagrams=diagrams,
            metadata=metadata,
        )

    def _detect_diagram_type(self, description: str) -> Optional[str]:
        """
        Detect diagram type from description.

        Args:
            description: Text description of the diagram.

        Returns:
            Detected diagram type or None.
        """
        description_lower = description.lower()

        if "bpmn" in description_lower:
            return "BPMN"
        elif "swimlane" in description_lower or "raia" in description_lower:
            return "Swimlane"
        elif "fluxo" in description_lower or "flowchart" in description_lower:
            return "Flowchart"
        elif "processo" in description_lower or "process" in description_lower:
            return "Process Diagram"
        else:
            return None

    def extract_to_dict(self, file_path: Path) -> dict:
        """
        Extract content and return as dictionary (for caching).

        Args:
            file_path: Path to the document file.

        Returns:
            Dictionary representation of extraction result.
        """
        result = self.extract(file_path)
        return result.model_dump(mode="json")
