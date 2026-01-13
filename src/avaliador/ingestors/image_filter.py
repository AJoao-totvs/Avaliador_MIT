"""
Image filter for identifying relevant diagrams.

Filters out logos, headers, icons and keeps only meaningful diagrams.
"""

from dataclasses import dataclass
from typing import Any, Protocol


# Minimum dimensions for a diagram (in pixels)
MIN_WIDTH = 200
MIN_HEIGHT = 200

# Minimum area for a diagram (in pixels^2)
MIN_AREA = 40000

# Aspect ratio thresholds (to filter out banners and logos)
MIN_ASPECT_RATIO = 0.2  # Very tall images
MAX_ASPECT_RATIO = 5.0  # Very wide images


class PictureItemProtocol(Protocol):
    """Protocol for Docling PictureItem-like objects."""

    @property
    def image(self) -> Any: ...


@dataclass
class ImageAnalysis:
    """Result of image analysis for filtering."""

    is_relevant: bool
    reason: str
    width: int = 0
    height: int = 0
    area: int = 0
    aspect_ratio: float = 0.0


class ImageFilter:
    """
    Filters images to identify relevant diagrams.

    Uses heuristics based on size, aspect ratio, and position to
    distinguish diagrams from logos, headers, and decorative images.
    """

    def __init__(
        self,
        min_width: int = MIN_WIDTH,
        min_height: int = MIN_HEIGHT,
        min_area: int = MIN_AREA,
        min_aspect_ratio: float = MIN_ASPECT_RATIO,
        max_aspect_ratio: float = MAX_ASPECT_RATIO,
    ):
        """
        Initialize image filter with thresholds.

        Args:
            min_width: Minimum width in pixels.
            min_height: Minimum height in pixels.
            min_area: Minimum area in pixels^2.
            min_aspect_ratio: Minimum width/height ratio.
            max_aspect_ratio: Maximum width/height ratio.
        """
        self.min_width = min_width
        self.min_height = min_height
        self.min_area = min_area
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio

    def analyze(self, width: int, height: int) -> ImageAnalysis:
        """
        Analyze an image to determine if it's a relevant diagram.

        Args:
            width: Image width in pixels.
            height: Image height in pixels.

        Returns:
            ImageAnalysis with relevance decision and reason.
        """
        area = width * height
        aspect_ratio = width / height if height > 0 else 0

        # Check minimum dimensions
        if width < self.min_width:
            return ImageAnalysis(
                is_relevant=False,
                reason=f"Width {width}px < minimum {self.min_width}px",
                width=width,
                height=height,
                area=area,
                aspect_ratio=aspect_ratio,
            )

        if height < self.min_height:
            return ImageAnalysis(
                is_relevant=False,
                reason=f"Height {height}px < minimum {self.min_height}px",
                width=width,
                height=height,
                area=area,
                aspect_ratio=aspect_ratio,
            )

        # Check minimum area
        if area < self.min_area:
            return ImageAnalysis(
                is_relevant=False,
                reason=f"Area {area}px^2 < minimum {self.min_area}px^2",
                width=width,
                height=height,
                area=area,
                aspect_ratio=aspect_ratio,
            )

        # Check aspect ratio (filter banners and logos)
        if aspect_ratio < self.min_aspect_ratio:
            return ImageAnalysis(
                is_relevant=False,
                reason=f"Aspect ratio {aspect_ratio:.2f} < minimum {self.min_aspect_ratio}",
                width=width,
                height=height,
                area=area,
                aspect_ratio=aspect_ratio,
            )

        if aspect_ratio > self.max_aspect_ratio:
            return ImageAnalysis(
                is_relevant=False,
                reason=f"Aspect ratio {aspect_ratio:.2f} > maximum {self.max_aspect_ratio}",
                width=width,
                height=height,
                area=area,
                aspect_ratio=aspect_ratio,
            )

        # Passed all filters
        return ImageAnalysis(
            is_relevant=True,
            reason="Image meets all criteria for a diagram",
            width=width,
            height=height,
            area=area,
            aspect_ratio=aspect_ratio,
        )

    def filter_pictures(self, pictures: list[Any]) -> list[Any]:
        """
        Filter a list of Docling PictureItem objects.

        Args:
            pictures: List of PictureItem-like objects.

        Returns:
            Filtered list containing only relevant diagrams.
        """
        relevant = []

        for pic in pictures:
            # Skip if no image data
            if not hasattr(pic, "image") or pic.image is None:
                continue

            # Get dimensions
            try:
                if hasattr(pic.image, "size"):
                    size = pic.image.size
                    if hasattr(size, "width") and hasattr(size, "height"):
                        width = size.width
                        height = size.height
                    elif isinstance(size, tuple) and len(size) >= 2:
                        width, height = size[0], size[1]
                    else:
                        continue
                else:
                    continue
            except (AttributeError, TypeError):
                continue

            # Analyze and filter
            analysis = self.analyze(width, height)
            if analysis.is_relevant:
                relevant.append(pic)

        return relevant


# Convenience function
def filter_relevant_images(pictures: list[Any]) -> list[Any]:
    """
    Filter images to keep only relevant diagrams.

    Args:
        pictures: List of PictureItem-like objects.

    Returns:
        Filtered list containing only relevant diagrams.
    """
    return ImageFilter().filter_pictures(pictures)
