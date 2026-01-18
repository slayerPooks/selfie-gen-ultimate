"""Check which required packages are installed in conda environment."""
import sys

required_packages = {
    "requests": "requests",
    "PIL": "Pillow", 
    "rich": "rich",
    "selenium": "selenium",
    "webdriver_manager": "webdriver-manager"
}

print("Checking required packages in conda environment...")
print(f"Python: {sys.version}")
print(f"Python executable: {sys.executable}")
print("\n" + "="*60)

missing = []
installed = []

for import_name, package_name in required_packages.items():
    try:
        __import__(import_name)
        installed.append(f"✅ {package_name}")
    except ImportError:
        missing.append(package_name)
        print(f"❌ {package_name} - NOT INSTALLED")

if installed:
    print("\n" + "="*60)
    print("Installed packages:")
    for pkg in installed:
        print(pkg)

if missing:
    print("\n" + "="*60)
    print("MISSING PACKAGES - Install with:")
    print(f"conda install -y {' '.join(missing)}")
    print("\nOr with pip:")
    print(f"pip install {' '.join(missing)}")
else:
    print("\n" + "="*60)
    print("✅ All required packages are installed!")
