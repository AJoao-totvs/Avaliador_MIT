"""
Reference manager for good MIT samples.

Loads and caches excerpts from high-quality MIT documents (8+ rating)
to use as few-shot examples in evaluation prompts.
"""

import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default samples directory (relative to project root)
DEFAULT_SAMPLES_DIR = Path(__file__).parent.parent.parent.parent / "samples" / "boas"

# Cache directory for extracted references
REFERENCES_CACHE_DIR = Path(__file__).parent / "references_cache"


class ReferenceManager:
    """
    Manages reference samples from good MIT documents.

    Extracts and caches key sections from 8+ rated MITs to use
    as comparison examples in evaluation prompts.
    """

    def __init__(
        self,
        samples_dir: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize reference manager.

        Args:
            samples_dir: Directory containing good samples. Defaults to samples/boas.
            cache_dir: Directory for caching extractions. Defaults to knowledge_base/references_cache.
        """
        self.samples_dir = samples_dir or DEFAULT_SAMPLES_DIR
        self.cache_dir = cache_dir or REFERENCES_CACHE_DIR
        self._references: dict[str, list[dict]] = {}

    def _get_cache_path(self, mit_type: str) -> Path:
        """Get cache file path for a MIT type."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir / f"{mit_type.lower()}_references.json"

    def _get_samples_hash(self, mit_type: str) -> str:
        """Calculate hash of all sample files for cache invalidation."""
        samples_path = self.samples_dir / mit_type.lower()
        if not samples_path.exists():
            return ""

        hasher = hashlib.sha256()
        for docx_file in sorted(samples_path.glob("*.docx")):
            hasher.update(docx_file.name.encode())
            hasher.update(str(docx_file.stat().st_mtime).encode())
        return hasher.hexdigest()[:16]

    def _load_cached_references(self, mit_type: str) -> Optional[dict]:
        """Load references from cache if valid."""
        cache_path = self._get_cache_path(mit_type)
        if not cache_path.exists():
            return None

        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("hash") == self._get_samples_hash(mit_type):
                return cached
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _save_to_cache(self, mit_type: str, references: list[dict]) -> None:
        """Save extracted references to cache."""
        cache_path = self._get_cache_path(mit_type)
        cache_data = {
            "hash": self._get_samples_hash(mit_type),
            "mit_type": mit_type,
            "references": references,
        }
        cache_path.write_text(
            json.dumps(cache_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _extract_key_sections(self, markdown: str, source_name: str) -> dict:
        """
        Extract key sections from a MIT document.

        Identifies and extracts representative sections that demonstrate
        quality patterns for each evaluation pillar.
        """
        sections = {
            "source": source_name,
            "excerpts": [],
        }

        lines = markdown.split("\n")
        current_section = []
        current_title = ""
        in_table = False

        for i, line in enumerate(lines):
            # Detect section headers
            if line.startswith("#") or line.startswith("**") and line.endswith("**"):
                # Save previous section if valuable
                if current_section and len(current_section) > 3:
                    section_text = "\n".join(current_section)
                    # Keep sections with tables or substantial content
                    if "|" in section_text or len(section_text) > 200:
                        sections["excerpts"].append({
                            "title": current_title,
                            "content": section_text[:2000],  # Limit size
                        })
                current_section = [line]
                current_title = line.strip("#* ")
            else:
                current_section.append(line)

            # Track tables
            if "|" in line and "-" in line:
                in_table = True

        # Add last section
        if current_section and len(current_section) > 3:
            section_text = "\n".join(current_section)
            if "|" in section_text or len(section_text) > 200:
                sections["excerpts"].append({
                    "title": current_title,
                    "content": section_text[:2000],
                })

        return sections

    def load_references(self, mit_type: str = "mit41") -> list[dict]:
        """
        Load reference excerpts for a MIT type.

        Args:
            mit_type: Type of MIT (e.g., "mit41", "MIT041").

        Returns:
            List of reference dictionaries with excerpts from good samples.
        """
        # Normalize MIT type
        mit_type_normalized = mit_type.lower().replace("mit", "").replace("0", "")
        mit_dir_name = f"mit{mit_type_normalized}"

        # Check cache first
        cached = self._load_cached_references(mit_dir_name)
        if cached:
            logger.info(f"Loaded {len(cached['references'])} cached references for {mit_type}")
            return cached["references"]

        # Find samples directory
        samples_path = self.samples_dir / mit_dir_name
        if not samples_path.exists():
            logger.warning(f"No samples directory found: {samples_path}")
            return []

        # Get all DOCX files
        docx_files = list(samples_path.glob("*.docx"))
        if not docx_files:
            logger.warning(f"No DOCX files found in {samples_path}")
            return []

        logger.info(f"Extracting references from {len(docx_files)} good samples...")

        # Extract each sample
        references = []
        try:
            from avaliador.ingestors.docling_extractor import DoclingExtractor
            extractor = DoclingExtractor(enable_vision=False)

            for docx_file in docx_files:
                try:
                    logger.info(f"Extracting: {docx_file.name}")
                    result = extractor.extract(docx_file)
                    sections = self._extract_key_sections(
                        result.markdown,
                        docx_file.stem,
                    )
                    if sections["excerpts"]:
                        references.append(sections)
                except Exception as e:
                    logger.warning(f"Failed to extract {docx_file.name}: {e}")

        except ImportError:
            logger.warning("Docling not available, cannot extract references")
            return []

        # Cache results
        if references:
            self._save_to_cache(mit_dir_name, references)
            logger.info(f"Cached {len(references)} references for {mit_type}")

        return references

    def get_reference_prompt_section(
        self,
        mit_type: str = "mit41",
        max_excerpts: int = 6,
        max_chars: int = 8000,
    ) -> str:
        """
        Generate a prompt section with reference examples.

        Args:
            mit_type: Type of MIT.
            max_excerpts: Maximum number of excerpts to include.
            max_chars: Maximum total characters for references.

        Returns:
            Formatted prompt section with reference examples.
        """
        references = self.load_references(mit_type)
        if not references:
            return ""

        prompt_parts = [
            "\n## EXEMPLOS DE REFERENCIA (MITs nota 8+)\n",
            "Os trechos abaixo sao de documentos MIT aprovados com nota >= 8.0.",
            "Use-os como referencia de qualidade e padrao esperado:\n",
        ]

        total_chars = 0
        excerpt_count = 0

        for ref in references:
            if excerpt_count >= max_excerpts:
                break

            for excerpt in ref["excerpts"]:
                if excerpt_count >= max_excerpts or total_chars >= max_chars:
                    break

                content = excerpt["content"]
                if total_chars + len(content) > max_chars:
                    # Truncate to fit
                    remaining = max_chars - total_chars
                    if remaining < 500:
                        break
                    content = content[:remaining] + "\n[...]"

                prompt_parts.append(f"\n### Referencia: {excerpt['title']}")
                prompt_parts.append(f"Fonte: {ref['source']}")
                prompt_parts.append("```")
                prompt_parts.append(content)
                prompt_parts.append("```\n")

                total_chars += len(content)
                excerpt_count += 1

        if excerpt_count == 0:
            return ""

        prompt_parts.append(
            "\n**INSTRUCAO**: Compare o documento em avaliacao com estes exemplos. "
            "Documentos de qualidade similar devem receber nota >= 8.0.\n"
        )

        return "\n".join(prompt_parts)


# Global instance for convenience
_reference_manager: Optional[ReferenceManager] = None


def get_reference_manager() -> ReferenceManager:
    """Get or create global reference manager instance."""
    global _reference_manager
    if _reference_manager is None:
        _reference_manager = ReferenceManager()
    return _reference_manager


def get_references(mit_type: str = "mit41") -> list[dict]:
    """Convenience function to load references."""
    return get_reference_manager().load_references(mit_type)


def get_reference_prompt(
    mit_type: str = "mit41",
    max_excerpts: int = 6,
    max_chars: int = 8000,
) -> str:
    """Convenience function to get reference prompt section."""
    return get_reference_manager().get_reference_prompt_section(
        mit_type, max_excerpts, max_chars
    )
