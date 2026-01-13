"""
Cache manager for document extractions.

Uses file-based caching with SHA256 hash of document content as key.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from avaliador.config import settings
from avaliador.models.schemas import ExtractionResult


class CacheManager:
    """Manages caching of document extractions."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory for cache storage. Defaults to settings.cache_dir.
        """
        self.cache_dir = cache_dir or settings.cache_dir
        self.enabled = settings.cache_enabled

    def _get_file_hash(self, file_path: Path) -> str:
        """Generate SHA256 hash of file content."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _get_cache_path(self, file_hash: str) -> Path:
        """Get cache file path for a given hash."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir / f"{file_hash}.json"

    def get(self, file_path: Path) -> Optional[dict]:
        """
        Get cached extraction for a file.

        Args:
            file_path: Path to the document file.

        Returns:
            Cached extraction dict if found, None otherwise.
        """
        if not self.enabled:
            return None

        file_hash = self._get_file_hash(file_path)
        cache_path = self._get_cache_path(file_hash)

        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                # Invalid cache, remove it
                cache_path.unlink(missing_ok=True)
                return None
        return None

    def save(self, file_path: Path, extraction: dict) -> None:
        """
        Save extraction to cache.

        Args:
            file_path: Path to the original document file.
            extraction: Extraction result dict to cache.
        """
        if not self.enabled:
            return

        file_hash = self._get_file_hash(file_path)
        cache_path = self._get_cache_path(file_hash)

        # Add cache metadata
        extraction["_cache_metadata"] = {
            "cached_at": datetime.now().isoformat(),
            "source_file": str(file_path),
            "file_hash": file_hash,
        }

        cache_path.write_text(
            json.dumps(extraction, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def clear(self) -> int:
        """
        Clear all cached extractions.

        Returns:
            Number of cache files removed.
        """
        count = 0
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
                count += 1
        return count


# Convenience functions for backwards compatibility
_cache_manager: Optional[CacheManager] = None


def _get_cache_manager() -> CacheManager:
    """Get or create global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def get_cached_extraction(file_path: Path) -> Optional[dict]:
    """Get cached extraction for a file."""
    return _get_cache_manager().get(file_path)


def save_extraction(file_path: Path, extraction: dict) -> None:
    """Save extraction to cache."""
    _get_cache_manager().save(file_path, extraction)
