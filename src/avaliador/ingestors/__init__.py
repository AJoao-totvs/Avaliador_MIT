"""Ingestors module for document extraction."""

from avaliador.ingestors.docling_extractor import DoclingExtractor
from avaliador.ingestors.image_filter import ImageFilter, filter_relevant_images

__all__ = ["DoclingExtractor", "ImageFilter", "filter_relevant_images"]
