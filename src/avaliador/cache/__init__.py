"""Cache module for storing document extractions."""

from avaliador.cache.manager import CacheManager, get_cached_extraction, save_extraction

__all__ = ["CacheManager", "get_cached_extraction", "save_extraction"]
