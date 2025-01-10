import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger


class PromptCache:
    def __init__(self, cache_dir: str = "/tmp/aider_cache/prompts", cache_ttl_days: int = 30):
        self.cache_dir = Path(cache_dir)
        self.cache_ttl = timedelta(days=cache_ttl_days)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"Initialized prompt cache at {self.cache_dir} with TTL of {cache_ttl_days} days"
        )

    def _get_cache_key(self, prompt: str, model_name: str) -> str:
        """Generate a unique cache key based on the prompt and model."""
        import hashlib

        # Create a unique key based on both prompt and model name
        combined = f"{prompt}:{model_name}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def _is_cache_valid(self, timestamp: datetime) -> bool:
        """Check if the cache entry is still valid based on TTL."""
        return datetime.now() - timestamp <= self.cache_ttl

    def get(self, prompt: str, model_name: str) -> Optional[str]:
        """Retrieve a cached response for a given prompt and model."""
        cache_key = self._get_cache_key(prompt, model_name)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r") as f:
                cache_data = json.load(f)
                timestamp = datetime.fromisoformat(cache_data["timestamp"])

                if not self._is_cache_valid(timestamp):
                    logger.info(f"Cache entry expired for key {cache_key}")
                    cache_file.unlink()
                    return None

                logger.info(f"Cache hit for prompt with key {cache_key}")
                return cache_data["response"]
        except Exception as e:
            logger.error(f"Error reading cache file {cache_file}: {e}")
            return None

    def store(self, prompt: str, model_name: str, response: str) -> None:
        """Store a prompt-response pair in the cache."""
        cache_key = self._get_cache_key(prompt, model_name)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            cache_data = {
                "prompt": prompt,
                "model_name": model_name,
                "response": response,
                "timestamp": datetime.now().isoformat(),
            }
            with open(cache_file, "w") as f:
                json.dump(cache_data, f)
            logger.info(f"Stored response in cache with key {cache_key}")
        except Exception as e:
            logger.error(f"Error writing to cache file {cache_file}: {e}")

    def clear(self) -> None:
        """Clear all cached prompts."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("Cleared prompt cache")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

    def cleanup_expired(self) -> None:
        """Remove all expired cache entries."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, "r") as f:
                        cache_data = json.load(f)
                        timestamp = datetime.fromisoformat(cache_data["timestamp"])
                        if not self._is_cache_valid(timestamp):
                            cache_file.unlink()
                            logger.info(f"Removed expired cache entry: {cache_file.name}")
                except Exception as e:
                    logger.error(f"Error processing cache file {cache_file}: {e}")
                    cache_file.unlink()  # Remove corrupted cache files
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")
