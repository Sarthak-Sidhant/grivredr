#!/usr/bin/env python3
"""
Verify Grivredr installation and setup
"""
import sys
import os
from pathlib import Path


def check_python():
    """Check Python version"""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor} (need 3.8+)")
        return False


def check_dependencies():
    """Check if required packages are installed"""
    print("\n📦 Checking dependencies...")

    required = [
        "playwright",
        "openai",
        "dotenv",
        "asyncio",
        "pathlib"
    ]

    missing = []
    for package in required:
        try:
            if package == "dotenv":
                __import__("dotenv")
            else:
                __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} (missing)")
            missing.append(package)

    return len(missing) == 0, missing


def check_playwright_browsers():
    """Check if Playwright browsers are installed"""
    print("\n🌐 Checking Playwright browsers...")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Try to launch chromium
            browser = p.chromium.launch(headless=True)
            browser.close()
            print("   ✅ Chromium browser installed")
            return True
    except Exception as e:
        print(f"   ❌ Chromium browser not found")
        print(f"      Error: {str(e)}")
        return False


def check_env_file():
    """Check if .env file exists and has API key"""
    print("\n🔑 Checking configuration...")

    if not Path(".env").exists():
        print("   ❌ .env file not found")
        print("      Run: cp .env.example .env")
        return False

    print("   ✅ .env file exists")

    # Check if API key is set
    with open(".env") as f:
        content = f.read()
        if "api_key=" in content and "your_megallm_api_key_here" not in content:
            # Mask the key for security
            print("   ✅ API key configured")
            return True
        else:
            print("   ⚠️  API key not set (using placeholder)")
            print("      Edit .env and add your MegaLLM API key")
            return False


def check_directory_structure():
    """Check if required directories exist"""
    print("\n📁 Checking directory structure...")

    required_dirs = [
        "agents",
        "cli",
        "config",
        "utils",
        "outputs",
        "data",
        "tests",
        "scripts",
        "docs"
    ]

    all_good = True
    for dir_name in required_dirs:
        if Path(dir_name).exists():
            print(f"   ✅ {dir_name}/")
        else:
            print(f"   ❌ {dir_name}/ (missing)")
            all_good = False

    return all_good


def check_key_files():
    """Check if key files exist"""
    print("\n📄 Checking key files...")

    key_files = [
        "cli/train_cli.py",
        "agents/orchestrator.py",
        "config/ai_client.py",
        "requirements.txt",
        "README.md"
    ]

    all_good = True
    for file_path in key_files:
        if Path(file_path).exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} (missing)")
            all_good = False

    return all_good


def main():
    """Run all checks"""
    print("="*60)
    print("🔍 Grivredr Setup Verification")
    print("="*60)

    results = []

    # Run checks
    results.append(("Python version", check_python()))

    deps_ok, missing = check_dependencies()
    results.append(("Dependencies", deps_ok))

    results.append(("Playwright browsers", check_playwright_browsers()))
    results.append(("Environment config", check_env_file()))
    results.append(("Directory structure", check_directory_structure()))
    results.append(("Key files", check_key_files()))

    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)

    passed = sum(1 for _, status in results if status)
    total = len(results)

    for check, status in results:
        icon = "✅" if status else "❌"
        print(f"{icon} {check}")

    print(f"\n{passed}/{total} checks passed")

    if passed == total:
        print("\n🎉 Setup complete! You're ready to start training!")
        print("\nNext steps:")
        print("  python cli/train_cli.py abua_sathi --district ranchi")
    else:
        print("\n⚠️  Setup incomplete. Please fix the issues above.")

        if not deps_ok:
            print("\n📥 To install dependencies:")
            print("  pip install -r requirements.txt")
            print("  python -m playwright install chromium")

        if not results[3][1]:  # env file check
            print("\n🔑 To configure API key:")
            print("  cp .env.example .env")
            print("  # Edit .env and add your API key")

    print("\n" + "="*60)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
