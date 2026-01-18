"""Test script to verify GUI can import generator after cache clearing."""
import sys

print(f"Python version: {sys.version}")
print("\nImporting GUI module...")

try:
    from kling_gui.main_window import HAS_GENERATOR
    print(f"✅ GUI module imported successfully")
    print(f"HAS_GENERATOR = {HAS_GENERATOR}")
    
    if HAS_GENERATOR:
        print("\n✅ SUCCESS! Generator is available to GUI")
        from kling_generator_falai import FalAIKlingGenerator
        print(f"Generator class: {FalAIKlingGenerator}")
    else:
        print("\n❌ FAILURE! Generator is NOT available to GUI")
        print("The import failed silently in main_window.py")
        
except Exception as e:
    print(f"❌ Error importing GUI module: {e}")
    import traceback
    traceback.print_exc()
