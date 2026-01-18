"""Test duration validation with improved MODEL_DURATION_CONSTRAINTS."""

import sys
sys.path.insert(0, 'kling_gui')

from queue_manager import validate_duration, MODEL_DURATION_CONSTRAINTS, get_duration_options_for_model

# Test cases from the implementation plan
test_cases = [
    # (model, duration, should_pass, description)
    ("fal-ai/kling-video/v2.5-turbo/pro/image-to-video", 5, True, "Kling 2.5 Turbo Pro @ 5s"),
    ("fal-ai/kling-video/v2.5-turbo/pro/image-to-video", 10, True, "Kling 2.5 Turbo Pro @ 10s"),
    ("fal-ai/kling-video/v2.5-turbo/pro/image-to-video", 15, False, "Kling 2.5 Turbo Pro @ 15s (invalid)"),

    ("fal-ai/wan/v2.6/image-to-video", 5, True, "Wan 2.6 @ 5s"),
    ("fal-ai/wan/v2.6/image-to-video", 10, True, "Wan 2.6 @ 10s"),
    ("fal-ai/wan/v2.6/image-to-video", 15, True, "Wan 2.6 @ 15s (NEW!)"),
    ("fal-ai/wan/v2.6/image-to-video", 20, False, "Wan 2.6 @ 20s (invalid)"),

    ("fal-ai/pixverse/v5/image-to-video", 5, True, "Pixverse V5 @ 5s"),
    ("fal-ai/pixverse/v5/image-to-video", 8, True, "Pixverse V5 @ 8s"),
    ("fal-ai/pixverse/v5/image-to-video", 4, False, "Pixverse V5 @ 4s (invalid)"),
    ("fal-ai/pixverse/v5/image-to-video", 10, False, "Pixverse V5 @ 10s (invalid)"),

    ("fal-ai/veo3/image-to-video", 5, True, "Veo 3 @ 5s"),
    ("fal-ai/veo3/image-to-video", 6, True, "Veo 3 @ 6s"),
    ("fal-ai/veo3/image-to-video", 7, True, "Veo 3 @ 7s"),
    ("fal-ai/veo3/image-to-video", 8, True, "Veo 3 @ 8s"),
    ("fal-ai/veo3/image-to-video", 9, False, "Veo 3 @ 9s (invalid)"),

    ("fal-ai/vidu/image-to-video", 2, True, "Vidu Q2 @ 2s"),
    ("fal-ai/vidu/image-to-video", 5, True, "Vidu Q2 @ 5s"),
    ("fal-ai/vidu/image-to-video", 8, True, "Vidu Q2 @ 8s"),
    ("fal-ai/vidu/image-to-video", 9, False, "Vidu Q2 @ 9s (invalid)"),

    # Edge cases
    ("fal-ai/unknown-model/image-to-video", 100, True, "Unknown model @ 100s (graceful degradation)"),
    ("fal-ai/kling-video/v2.1/pro/image-to-video", 0, False, "Kling 2.1 @ 0s (invalid - non-positive)"),
    ("fal-ai/kling-video/v2.1/pro/image-to-video", -5, False, "Kling 2.1 @ -5s (invalid - negative)"),
]

print("Testing Duration Validation")
print("=" * 70)
print()

passed = 0
failed = 0

for model, duration, should_pass, description in test_cases:
    try:
        validate_duration(model, duration)
        result = "PASS"
        if not should_pass:
            result = "FAIL (should have raised error)"
            failed += 1
        else:
            passed += 1
    except ValueError as e:
        result = "PASS (error raised)"
        if should_pass:
            result = f"FAIL (unexpected error: {e})"
            failed += 1
        else:
            passed += 1

    status_icon = "✓" if "PASS" in result else "✗"
    print(f"{status_icon} {description}: {result}")

print()
print("=" * 70)
print("Testing get_duration_options_for_model()")
print("-" * 70)

# Test helper function
helper_tests = [
    ("fal-ai/kling-video/v2.5-turbo/pro/image-to-video", [5, 10]),
    ("fal-ai/wan/v2.6/image-to-video", [5, 10, 15]),
    ("fal-ai/pixverse/v5/image-to-video", [5, 8]),
    ("fal-ai/vidu/image-to-video", [2, 3, 4, 5, 6, 7, 8]),
    ("fal-ai/unknown-model", [5, 10]),  # Default for unknown
]

helper_passed = 0
helper_failed = 0

for endpoint, expected_options in helper_tests:
    result = get_duration_options_for_model(endpoint)
    if result == expected_options:
        print(f"✓ {endpoint}: {result}")
        helper_passed += 1
    else:
        print(f"✗ {endpoint}: expected {expected_options}, got {result}")
        helper_failed += 1

print()
print("=" * 70)
print(f"Validation Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
print(f"Helper Function Results: {helper_passed} passed, {helper_failed} failed out of {len(helper_tests)} tests")
print()

if failed == 0 and helper_failed == 0:
    print("✓ All tests PASSED!")
else:
    print(f"✗ {failed + helper_failed} tests FAILED")
    sys.exit(1)
