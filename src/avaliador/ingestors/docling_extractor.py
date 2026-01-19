"""
Document extractor using Docling library.

Extracts text, structure, and images from DOCX files.
Ensures full document extraction without any content limits.
"""

import io
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from avaliador.config import settings
from avaliador.ingestors.image_filter import ImageFilter
from avaliador.models.schemas import (
    DiagramDescription,
    ExtractionMetadata,
    ExtractionResult,
)

logger = logging.getLogger(__name__)

# Maximum size constant - ensures no artificial limits on extraction
MAX_SIZE = sys.maxsize


class DoclingExtractor:
    """
    Document extractor using Docling library.

    Supports DOCX extraction with optional VLM-based image description.
    """

    def __init__(
        self,
        enable_vision: bool = True,
        image_filter: Optional[ImageFilter] = None,
        llm_client: Optional[Any] = None,
    ):
        """
        Initialize extractor.

        Args:
            enable_vision: Whether to use VLM for image description.
            image_filter: Custom image filter. Defaults to standard filter.
            llm_client: Optional DTA Proxy client for VLM analysis.
        """
        self.enable_vision = enable_vision and settings.vision_enabled
        self.image_filter = image_filter or ImageFilter()
        self._converter = None
        self._llm_client = llm_client
        self._bpmn_prompt: Optional[str] = None

    @property
    def llm_client(self) -> Any:
        """Get or create LLM client for VLM analysis."""
        if self._llm_client is None and self.enable_vision:
            try:
                from avaliador.llm.dta_client import DTAProxyClient

                self._llm_client = DTAProxyClient()
            except Exception as e:
                logger.warning(f"Failed to initialize LLM client for vision: {e}")
                self._llm_client = None
        return self._llm_client

    def _get_image_analysis_prompt(self) -> str:
        """Load comprehensive image analysis prompt."""
        if self._bpmn_prompt is None:
            try:
                from avaliador.knowledge_base.loader import get_prompt

                self._bpmn_prompt = get_prompt("bpmn_analysis")
            except Exception:
                self._bpmn_prompt = (
                    "Analise esta imagem extraida de documentacao MIT041 (Desenho da Solucao). "
                    "PRIMEIRO identifique o tipo: DIAGRAMA, TABELA, CAPTURA DE TELA ou OUTRO. "
                    "DEPOIS extraia TODO o conteudo visivel com maximo detalhe. "
                    "Se for TABELA: liste todos os cabecalhos e transcreva TODAS as linhas de dados. "
                    "Se for DIAGRAMA: identifique tipo, eventos, gateways, raias e atividades. "
                    "Se for CAPTURA DE TELA: liste todos os campos e valores visiveis. "
                    "NAO RESUMA - extraia o conteudo completo e exaustivo."
                )
        return self._bpmn_prompt

    def _get_converter(self):
        """
        Lazy-load Docling converter configured for full document extraction.

        Uses SimplePipeline for DOCX files which provides direct parsing
        without artificial content limits.
        """
        if self._converter is None:
            try:
                from docling.datamodel.base_models import InputFormat
                from docling.document_converter import (
                    DocumentConverter,
                    WordFormatOption,
                )
                from docling.pipeline.simple_pipeline import SimplePipeline

                # Configure DOCX extraction with SimplePipeline for full content
                # SimplePipeline provides direct document parsing without limits
                format_options = {
                    InputFormat.DOCX: WordFormatOption(
                        pipeline_cls=SimplePipeline,
                    ),
                }

                # Create converter with explicit format options
                # allowed_formats ensures only supported formats are processed
                self._converter = DocumentConverter(
                    allowed_formats=[InputFormat.DOCX],
                    format_options=format_options,
                )

                logger.debug(
                    "Docling converter initialized with SimplePipeline for DOCX"
                )

            except ImportError as e:
                raise ImportError(
                    "Docling is not installed. Install with: pip install docling"
                ) from e

        return self._converter

    def extract(self, file_path: Path) -> ExtractionResult:
        """
        Extract content from a document.

        Extracts the FULL document content without any artificial limits.
        All pages and all content elements are included in the extraction.

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

        logger.info(f"Starting extraction of: {file_path.name}")

        # Convert document with explicit parameters to ensure full extraction
        # max_num_pages=MAX_SIZE ensures no page limit
        # max_file_size=MAX_SIZE ensures no file size limit
        result = converter.convert(
            str(file_path),
            max_num_pages=MAX_SIZE,
            max_file_size=MAX_SIZE,
        )
        doc = result.document

        # Export to markdown with explicit parameters for full content
        # from_element=0 starts from beginning
        # to_element=MAX_SIZE ensures all elements are included (no truncation)
        markdown = doc.export_to_markdown(
            from_element=0,
            to_element=MAX_SIZE,
        )

        logger.info(
            f"Extraction complete: {len(markdown)} characters, "
            f"approximately {len(markdown.split())} words"
        )

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

                # If no Docling description, try VLM analysis
                if not description and self.llm_client is not None:
                    description = self._describe_image_with_vlm(pic, i)

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

    def _describe_image_with_vlm(self, pic: Any, index: int) -> str:
        """
        Describe an image using VLM (Vision Language Model).

        Args:
            pic: Docling PictureItem object.
            index: Index of the image in the document.

        Returns:
            Description of the image or empty string if failed.
        """
        try:
            # Get image data
            if not hasattr(pic, "image") or pic.image is None:
                return ""

            # Convert PIL Image to bytes
            image = pic.image
            if hasattr(image, "pil_image"):
                image = image.pil_image

            # Convert to PNG bytes
            img_buffer = io.BytesIO()
            if hasattr(image, "save"):
                image.save(img_buffer, format="PNG")
                img_data = img_buffer.getvalue()
            elif hasattr(image, "tobytes"):
                img_data = image.tobytes()
            else:
                logger.warning(f"Cannot extract image data for diagram {index}")
                return ""

            # Call VLM with sufficient tokens for detailed content extraction
            # (tables, diagrams, screenshots all need comprehensive analysis)
            logger.info(f"Analyzing image {index + 1} with VLM...")
            description = self.llm_client.describe_image(
                image_data=img_data,
                prompt=self._get_image_analysis_prompt(),
                mime_type="image/png",
                max_tokens=4000,  # High limit for full table transcription
            )
            return description.strip()

        except Exception as e:
            logger.warning(f"VLM analysis failed for diagram {index}: {e}")
            return ""

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
