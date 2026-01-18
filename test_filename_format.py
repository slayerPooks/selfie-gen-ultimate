"""
Test script for enhanced filename format implementation.

Tests the new filename generation without making actual API calls.
"""

from datetime import datetime
from kling_generator_falai import FalAIKlingGenerator


def test_filename_generation():
    """Test the new filename generation logic."""
    print("=" * 80)
    print("Testing Enhanced Filename Format")
    print("=" * 80)

    # Create generator instance (with dummy API key since we're not making actual calls)
    generator = FalAIKlingGenerator(
        api_key="test_key",
        model_endpoint="fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
        model_display_name="Kling V2.5 Turbo Pro",
        prompt_slot=3,
        verbose=False,
    )

    # Test timestamp
    test_timestamp = datetime(2026, 1, 17, 14, 30, 0)

    # Test 1: With prompt shorthand (from prompt_titles)
    print("\n1. Test with prompt shorthand:")
    config_with_shorthand = {
        "prompt_titles": {
            "3": "Left Right 1-2-3-4-5-6"
        },
        "saved_prompts": {
            "3": "Full prompt text here..."
        }
    }

    filename1 = generator.get_output_filename("Selfie", config_with_shorthand, test_timestamp)
    print(f"   Result: {filename1}")
    expected1 = "Selfie-Kling_V2.5_Turbo_Pro-Left_Right_1-2-3-4-5-6-p3-01-17-2026.mp4"
    print(f"   Expected: {expected1}")
    print(f"   ✓ Match!" if filename1 == expected1 else f"   ✗ Mismatch!")

    # Test 2: Without shorthand (fallback to prompt text extraction)
    print("\n2. Test without shorthand (fallback to prompt extraction):")
    config_without_shorthand = {
        "prompt_titles": {},
        "saved_prompts": {
            "3": "Turn head to the right slowly then all the way to the left slowly. Make sure the body is kept still."
        }
    }

    filename2 = generator.get_output_filename("Portrait", config_without_shorthand, test_timestamp)
    print(f"   Result: {filename2}")
    print(f"   (Should extract first 3-5 meaningful words from prompt)")
    # Expected: "Portrait-Kling_V2.5_Turbo_Pro-Turn_head_right_slowly_way-p3-01-17-2026.mp4" (or similar)

    # Test 3: With different model
    print("\n3. Test with different model:")
    generator.update_model(
        "fal-ai/wan-25-preview/image-to-video",
        "Wan 2.5 Image to Video"
    )
    generator.update_prompt_slot(1)

    config_wan = {
        "prompt_titles": {
            "1": "Basic Blink"
        },
        "saved_prompts": {
            "1": "Subject blinks naturally"
        }
    }

    filename3 = generator.get_output_filename("Test", config_wan, test_timestamp)
    print(f"   Result: {filename3}")
    expected3 = "Test-Wan_2.5_Image_to_Video-Basic_Blink-p1-01-17-2026.mp4"
    print(f"   Expected: {expected3}")
    print(f"   ✓ Match!" if filename3 == expected3 else f"   ✗ Mismatch!")

    # Test 4: Empty config (should use defaults)
    print("\n4. Test with empty config (fallback to defaults):")
    filename4 = generator.get_output_filename("Image", {}, test_timestamp)
    print(f"   Result: {filename4}")
    print(f"   (Should use 'prompt' as fallback)")

    # Test 5: Sanitize special characters in prompt titles
    print("\n5. Test special character sanitization:")
    config_special = {
        "prompt_titles": {
            "1": "Left/Right & Up/Down!"
        },
        "saved_prompts": {
            "1": "Movement test"
        }
    }

    filename5 = generator.get_output_filename("Special", config_special, test_timestamp)
    print(f"   Result: {filename5}")
    print(f"   (Should remove special chars except underscores and dashes)")

    # Test 6: Test sanitize_prompt_description directly
    print("\n6. Test prompt text sanitization:")
    test_prompts = [
        "Generate a lifelike video animation with smooth movements",
        "Turn head to the right slowly then to the left",
        "Framing: medium shot, head and upper torso visible",
        "The subject should blink naturally and smile",
    ]

    for prompt in test_prompts:
        sanitized = generator._sanitize_prompt_description(prompt)
        print(f"   '{prompt[:50]}...'")
        print(f"   → {sanitized}")

    print("\n" + "=" * 80)
    print("Testing Complete!")
    print("=" * 80)


if __name__ == "__main__":
    test_filename_generation()
