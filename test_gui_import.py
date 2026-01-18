"""Diagnostic script to expose the hidden import error in GUI.

This script imports exactly as the GUI does and prints the full error
instead of silently catching it.
"""
import sys
import traceback

print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print("\nAttempting to import FalAIKlingGenerator...")
print("-" * 60)

try:
    from kling_generator_falai import FalAIKlingGenerator
    print("✅ Import succeeded!")
    print(f"Generator class: {FalAIKlingGenerator}")
    print(f"Generator module: {FalAIKlingGenerator.__module__}")
    print(f"Generator file: {FalAIKlingGenerator.__module__.__file__ if hasattr(FalAIKlingGenerator.__module__, '__file__') else 'N/A'}")
except Exception as e:
    print("❌ Import failed!")
    print(f"Error type: {type(e).__name__}")
    print(f"Error message: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    print("\n" + "=" * 60)
    print("DIAGNOSIS:")
    print("=" * 60)
    if isinstance(e, ImportError):
        print("This is an ImportError - likely missing dependency or module not found")
        print(f"Failed module: {e.name if hasattr(e, 'name') else 'unknown'}")
        print(f"Module path: {e.path if hasattr(e, 'path') else 'unknown'}")
    elif isinstance(e, SyntaxError):
        print("This is a SyntaxError - code has syntax issues")
        print(f"File: {e.filename}")
        print(f"Line: {e.lineno}")
    else:
        print(f"Unexpected error type: {type(e).__name__}")
