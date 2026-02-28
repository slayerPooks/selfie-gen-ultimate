"""
Model Schema Manager - Queries and caches fal.ai model capabilities
"""

import requests
import logging
import time
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
import json
from pathlib import Path

logger = logging.getLogger(__name__)

# Default cache TTL in seconds (1 hour)
DEFAULT_CACHE_TTL = 3600


@dataclass
class ModelParameter:
    """Represents a single model parameter"""

    name: str
    type: str
    required: bool
    description: str
    default: Any = None
    enum: Optional[List[Any]] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None


@dataclass
class CachedSchema:
    """Represents a cached schema with timestamp for TTL management"""

    parameters: Dict[str, ModelParameter] = field(default_factory=dict)
    timestamp: float = 0.0

    def is_expired(self, ttl: int = DEFAULT_CACHE_TTL) -> bool:
        """Check if the cache has expired based on TTL."""
        if self.timestamp == 0:
            return True
        return (time.time() - self.timestamp) > ttl


class ModelSchemaManager:
    """Manages model schemas and parameter detection with TTL-based caching"""

    def __init__(
        self,
        api_key: str,
        cache_dir: Optional[str] = None,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ):
        """
        Initialize the ModelSchemaManager.

        Args:
            api_key: fal.ai API key
            cache_dir: Directory for disk cache (default: ~/.kling-ui/model_cache)
            cache_ttl: Cache time-to-live in seconds (default: 3600 = 1 hour)
        """
        self.api_key = api_key
        self.cache_ttl = cache_ttl
        self.cache_dir = (
            Path(cache_dir) if cache_dir else Path.home() / ".kling-ui" / "model_cache"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, CachedSchema] = {}

    def get_model_schema(
        self, model_endpoint: str, use_cache: bool = True, force_refresh: bool = False
    ) -> Dict[str, ModelParameter]:
        """
        Fetch OpenAPI schema for a model endpoint.

        Args:
            model_endpoint: e.g., "fal-ai/kling-video/v2.1/pro/image-to-video"
            use_cache: Whether to use cached schema
            force_refresh: Force refresh even if cache is valid (bypasses TTL)

        Returns:
            Dictionary of parameter name -> ModelParameter
        """
        # Check memory cache first (unless force refresh)
        if not force_refresh and model_endpoint in self._memory_cache:
            cached = self._memory_cache[model_endpoint]
            if not cached.is_expired(self.cache_ttl):
                logger.debug(f"Using memory-cached schema for {model_endpoint}")
                return cached.parameters
            else:
                logger.debug(f"Memory cache expired for {model_endpoint}")

        # Check disk cache
        cache_file = self.cache_dir / f"{model_endpoint.replace('/', '_')}.json"
        if use_cache and not force_refresh and cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)

                # Check disk cache timestamp
                cache_timestamp = cached_data.get("_cache_timestamp", 0)
                if (
                    cache_timestamp
                    and (time.time() - cache_timestamp) <= self.cache_ttl
                ):
                    parameters = self._parse_cached_schema(cached_data)
                    # Store in memory cache
                    self._memory_cache[model_endpoint] = CachedSchema(
                        parameters=parameters, timestamp=cache_timestamp
                    )
                    logger.info(f"Loaded disk-cached schema for {model_endpoint}")
                    return parameters
                else:
                    logger.debug(f"Disk cache expired for {model_endpoint}")
            except Exception as e:
                logger.warning(f"Failed to load cached schema: {e}")

        # Fetch from API
        try:
            url = "https://api.fal.ai/v1/models"
            params = {"endpoint_id": model_endpoint, "expand": "openapi-3.0"}
            headers = {"Authorization": f"Key {self.api_key}"}

            logger.info(f"Fetching schema for {model_endpoint}...")
            response = requests.get(url, params=params, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.error(f"Failed to fetch schema: {response.status_code}")
                return self._get_fallback_schema()

            data = response.json()

            # Add cache timestamp to data before saving
            current_time = time.time()
            data["_cache_timestamp"] = current_time

            # Save to disk cache
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)

            # Parse schema
            parameters = self._parse_schema_response(data)

            # Store in memory cache
            self._memory_cache[model_endpoint] = CachedSchema(
                parameters=parameters, timestamp=current_time
            )

            logger.info(f"Fetched schema with {len(parameters)} parameters")
            return parameters

        except Exception as e:
            logger.error(f"Error fetching schema: {e}")
            return self._get_fallback_schema()

    def _parse_schema_response(self, data: dict) -> Dict[str, ModelParameter]:
        """Parse OpenAPI schema from API response"""
        parameters = {}

        try:
            # The API returns a list of models - we want the first one
            models_list = data.get("models", [])
            if not models_list:
                logger.warning("No models found in API response")
                return parameters

            model_data = models_list[0]

            # Navigate to the OpenAPI schema
            openapi = model_data.get("openapi", {})
            components = openapi.get("components", {})
            schemas = components.get("schemas", {})

            # Find the Input schema - it could be named "Input" or model-specific like
            # "KlingVideoV21ProImageToVideoInput"
            input_schema = None

            # First try "Input"
            if "Input" in schemas:
                input_schema = schemas["Input"]
            else:
                # Look for a schema that ends with "Input" and contains "properties"
                for schema_name, schema_data in schemas.items():
                    if schema_name.endswith("Input") and "properties" in schema_data:
                        input_schema = schema_data
                        logger.debug(f"Found input schema: {schema_name}")
                        break

            if not input_schema:
                logger.warning("Could not find Input schema in response")
                return parameters

            properties = input_schema.get("properties", {})
            required_fields = set(input_schema.get("required", []))

            for param_name, param_spec in properties.items():
                param = ModelParameter(
                    name=param_name,
                    type=param_spec.get("type", "string"),
                    required=param_name in required_fields,
                    description=param_spec.get("description", ""),
                    default=param_spec.get("default"),
                    enum=param_spec.get("enum"),
                    minimum=param_spec.get("minimum"),
                    maximum=param_spec.get("maximum"),
                )
                parameters[param_name] = param

            logger.info(f"Parsed {len(parameters)} parameters from schema")

        except Exception as e:
            logger.error(f"Error parsing schema: {e}")

        return parameters

    def _parse_cached_schema(self, data: dict) -> Dict[str, ModelParameter]:
        """Parse cached schema data"""
        return self._parse_schema_response(data)

    def _get_fallback_schema(self) -> Dict[str, ModelParameter]:
        """Return fallback schema with common parameters"""
        return {
            "image_url": ModelParameter("image_url", "string", True, "Input image URL"),
            "prompt": ModelParameter("prompt", "string", True, "Generation prompt"),
            "duration": ModelParameter(
                "duration", "integer", False, "Video duration", default=10
            ),
            "aspect_ratio": ModelParameter(
                "aspect_ratio", "string", False, "Aspect ratio", default="16:9"
            ),
        }

    def supports_parameter(self, model_endpoint: str, param_name: str) -> bool:
        """Check if a model supports a specific parameter"""
        schema = self.get_model_schema(model_endpoint)
        return param_name in schema

    def get_supported_parameters(self, model_endpoint: str) -> Set[str]:
        """Get set of all supported parameter names"""
        schema = self.get_model_schema(model_endpoint)
        return set(schema.keys())

    def get_parameter_info(
        self, model_endpoint: str, param_name: str
    ) -> Optional[ModelParameter]:
        """Get detailed info about a specific parameter"""
        schema = self.get_model_schema(model_endpoint)
        return schema.get(param_name)

    def validate_parameters(
        self, model_endpoint: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Filter parameters to only those supported by the model.

        Args:
            model_endpoint: Model endpoint identifier
            params: Dictionary of parameters to validate

        Returns:
            Filtered dictionary with only supported parameters
        """
        supported = self.get_supported_parameters(model_endpoint)
        validated = {}

        for key, value in params.items():
            if key in supported:
                validated[key] = value
            else:
                logger.warning(
                    f"Parameter '{key}' not supported by {model_endpoint}, skipping"
                )

        return validated

    def clear_cache(self, model_endpoint: Optional[str] = None):
        """
        Clear cached schemas.

        Args:
            model_endpoint: Specific model to clear, or None to clear all
        """
        if model_endpoint:
            # Clear specific model
            if model_endpoint in self._memory_cache:
                del self._memory_cache[model_endpoint]
            cache_file = self.cache_dir / f"{model_endpoint.replace('/', '_')}.json"
            if cache_file.exists():
                cache_file.unlink()
            logger.info(f"Cleared cache for {model_endpoint}")
        else:
            # Clear all caches
            self._memory_cache.clear()
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("Cleared all schema caches")

    def get_cache_info(self, model_endpoint: str) -> Dict[str, Any]:
        """
        Get cache status information for a model.

        Args:
            model_endpoint: Model endpoint to check

        Returns:
            Dictionary with cache status info
        """
        info = {
            "model": model_endpoint,
            "in_memory": model_endpoint in self._memory_cache,
            "on_disk": False,
            "expired": True,
            "age_seconds": None,
            "ttl_remaining": None,
        }

        # Check memory cache
        if model_endpoint in self._memory_cache:
            cached = self._memory_cache[model_endpoint]
            age = time.time() - cached.timestamp
            info["age_seconds"] = int(age)
            info["expired"] = cached.is_expired(self.cache_ttl)
            info["ttl_remaining"] = max(0, int(self.cache_ttl - age))

        # Check disk cache
        cache_file = self.cache_dir / f"{model_endpoint.replace('/', '_')}.json"
        if cache_file.exists():
            info["on_disk"] = True
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                    timestamp = data.get("_cache_timestamp", 0)
                    if timestamp:
                        age = time.time() - timestamp
                        info["disk_age_seconds"] = int(age)
            except Exception:
                pass

        return info

    def refresh_schema(self, model_endpoint: str) -> Dict[str, ModelParameter]:
        """
        Force refresh schema from API, bypassing cache.

        Args:
            model_endpoint: Model endpoint to refresh

        Returns:
            Fresh schema parameters
        """
        return self.get_model_schema(model_endpoint, use_cache=True, force_refresh=True)
