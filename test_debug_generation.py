#!/usr/bin/env python3
"""Debug script to test video generation with full logging output."""

import sys
import json
from pathlib import Path
from datetime import datetime
from kling_generator_falai import FalAIKlingGenerator

def load_config():
    """Load configuration from kling_config.json"""
    config_path = Path("kling_config.json")
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    else:
        print("ERROR: kling_config.json not found!")
        sys.exit(1)

def main():
    print("="*80)
    print("VIDEO GENERATION DEBUG TEST")
    print("="*80)

    # Load config
    config = load_config()
    api_key = config.get("falai_api_key", "")

    if not api_key:
        print("ERROR: No API key found in config!")
        sys.exit(1)

    print(f"\n✓ API key loaded: {api_key[:10]}...")
    print(f"✓ Model: {config.get('model_display_name', 'Unknown')}")
    print(f"✓ Prompt slot: {config.get('current_prompt_slot', 1)}")

    # Initialize generator
    generator = FalAIKlingGenerator(
        api_key=api_key,
        verbose=True,
        model_endpoint=config.get("current_model"),
        model_display_name=config.get("model_display_name"),
        prompt_slot=config.get("current_prompt_slot", 1)
    )

    print("\n✓ Generator initialized")

    # Test image path
    test_image = r"F:\iCloudDrive\F\kyc hunter\dash-01-08-26 Alyah Kanso\dash\item_11\selfie-gen-fill-expand.png"
    if not Path(test_image).exists():
        print(f"\nERROR: Test image not found: {test_image}")
        sys.exit(1)

    print(f"\n✓ Test image: {test_image}")
    print(f"\nStarting generation with DEBUG logging enabled...")
    print("="*80)
    print()

    # Generate video
    timestamp = datetime.now()
    result = generator.create_kling_generation(
        character_image_path=test_image,
        config=config,
        timestamp=timestamp
    )

    print()
    print("="*80)
    if result:
        print(f"✓ SUCCESS: Video saved to {result}")
    else:
        print("✗ FAILED: Video generation returned None")
        print("Check the error messages and traceback above")
    print("="*80)

if __name__ == "__main__":
    main()
