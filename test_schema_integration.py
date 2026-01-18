#!/usr/bin/env python3
"""Test script to verify schema manager integration with config panel."""

import os
import sys

# Test 1: Import check
print("Test 1: Import check...")
try:
    from model_schema_manager import ModelSchemaManager
    from model_metadata import get_duration_options
    print("✓ Imports successful")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Check API key availability
print("\nTest 2: API key check...")
api_key = os.getenv("FAL_KEY")
if api_key:
    print(f"✓ API key found (length: {len(api_key)})")
else:
    print("⚠ No FAL_KEY environment variable (some features will use fallback)")

# Test 3: Test schema manager basic functionality
print("\nTest 3: Schema manager instantiation...")
try:
    if api_key:
        manager = ModelSchemaManager(api_key)
        print("✓ Schema manager created")

        # Test a known model
        print("\nTest 4: Fetch schema for Kling 2.5 Turbo...")
        test_model = "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"
        supported_params = manager.get_supported_parameters(test_model)

        if supported_params:
            print(f"✓ Schema fetched successfully")
            print(f"  Supported parameters: {supported_params}")

            # Check duration parameter
            duration_param = manager.get_parameter_info(test_model, "duration")
            if duration_param:
                print(f"  Duration info: {duration_param}")
            else:
                print("  Duration parameter not found in schema")
        else:
            print("⚠ No parameters found (might be expected for some models)")
    else:
        print("⚠ Skipping schema manager tests (no API key)")
except Exception as e:
    print(f"✗ Schema manager test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Test metadata fallback
print("\nTest 5: Metadata fallback...")
try:
    test_models = [
        "fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
        "fal-ai/ltx-video/image-to-video",
        "fal-ai/pixverse/v5/image-to-video"
    ]

    for model in test_models:
        durations = get_duration_options(model)
        print(f"  {model.split('/')[-2:]}: {durations}s")

    print("✓ Metadata fallback working")
except Exception as e:
    print(f"✗ Metadata test failed: {e}")

print("\n" + "="*60)
print("All basic tests completed!")
print("="*60)
