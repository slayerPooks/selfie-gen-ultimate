#!/usr/bin/env python3
"""
Test script for model schema detection functionality.

Usage:
    python test_schema_detection.py

Requires FAL_KEY environment variable to be set.
"""

import os
import sys


def test_schema_manager():
    """Test the ModelSchemaManager functionality."""
    from model_schema_manager import (
        ModelSchemaManager,
        ModelParameter,
        DEFAULT_CACHE_TTL,
    )
    import json
    import time

    # Try environment variable first, then config file
    api_key = os.getenv("FAL_KEY")
    if not api_key:
        config_path = os.path.join(os.path.dirname(__file__), "kling_config.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
                api_key = config.get("falai_api_key", "")

    if not api_key:
        print("ERROR: FAL_KEY environment variable not set and not found in config")
        print("Set it with: set FAL_KEY=your_api_key")
        sys.exit(1)

    print("=" * 60)
    print("MODEL SCHEMA DETECTION TEST")
    print("=" * 60)
    print()

    manager = ModelSchemaManager(api_key)

    # Test models
    test_models = [
        "fal-ai/kling-video/v2.1/pro/image-to-video",
        "fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
        "fal-ai/bytedance/seedance/v1.5/pro/image-to-video",
    ]

    for model_id in test_models:
        print(f"Testing: {model_id}")
        print("-" * 60)

        schema = manager.get_model_schema(model_id)

        if not schema:
            print("  WARNING: No schema returned")
            print()
            continue

        print(f"  Parameters found: {len(schema)}")

        # Check key parameters
        key_params = [
            "seed",
            "aspect_ratio",
            "duration",
            "cfg_scale",
            "negative_prompt",
        ]
        print("  Key parameter support:")
        for param in key_params:
            supported = manager.supports_parameter(model_id, param)
            status = "✓" if supported else "✗"
            print(f"    {status} {param}")

        # Show all parameter names
        print(f"  All parameters: {', '.join(sorted(schema.keys()))}")
        print()

    # Test parameter validation
    print("=" * 60)
    print("PARAMETER VALIDATION TEST")
    print("=" * 60)
    print()

    test_params = {
        "image_url": "https://example.com/image.jpg",
        "prompt": "A character walking",
        "duration": 10,
        "seed": 42,
        "aspect_ratio": "16:9",
        "fake_param": "should be removed",
        "another_fake": 123,
    }

    model = "fal-ai/kling-video/v2.1/pro/image-to-video"
    print(f"Model: {model}")
    print(f"Input params: {list(test_params.keys())}")

    validated = manager.validate_parameters(model, test_params)
    print(f"Validated params: {list(validated.keys())}")

    removed = set(test_params.keys()) - set(validated.keys())
    if removed:
        print(f"Removed params: {removed}")

    # Test cache TTL functionality
    print()
    print("=" * 60)
    print("CACHE TTL TEST")
    print("=" * 60)
    print()

    print(
        f"Default TTL: {DEFAULT_CACHE_TTL} seconds ({DEFAULT_CACHE_TTL // 60} minutes)"
    )

    # Get cache info for first model
    cache_info = manager.get_cache_info(test_models[0])
    print(f"\nCache info for {test_models[0]}:")
    print(f"  In memory: {cache_info['in_memory']}")
    print(f"  On disk: {cache_info['on_disk']}")
    print(f"  Expired: {cache_info['expired']}")
    if cache_info.get("age_seconds") is not None:
        print(f"  Age: {cache_info['age_seconds']} seconds")
        print(f"  TTL remaining: {cache_info['ttl_remaining']} seconds")

    print()
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_schema_manager()
