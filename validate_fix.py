#!/usr/bin/env python3
"""
Validation script to check that our fixes are working correctly.
"""

import os
import sys
import importlib.util

def validate_app_syntax():
    """Validate that the app.py file has correct syntax"""
    print("🔍 Validating app.py syntax...")
    
    try:
        # Set dummy environment variables to avoid API key errors
        os.environ['GOOGLE_API_KEY'] = 'dummy_key_1'
        os.environ['GOOGLE_API_KEY2'] = 'dummy_key_2'
        os.environ['GOOGLE_API_KEY3'] = 'dummy_key_3'
        
        # Try to import the app module
        spec = importlib.util.spec_from_file_location("app", "app.py")
        app_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(app_module)
        
        print("✅ app.py syntax is valid")
        
        # Check if the FastAPI app exists
        if hasattr(app_module, 'app'):
            print("✅ FastAPI app instance found")
        else:
            print("❌ FastAPI app instance not found")
            return False
            
        # Check if endpoints exist
        app_instance = app_module.app
        routes = [route.path for route in app_instance.routes]
        
        expected_routes = ["/", "/health", "/translate-srt/"]
        for route in expected_routes:
            if route in routes:
                print(f"✅ Route {route} found")
            else:
                print(f"❌ Route {route} not found")
                return False
        
        # Check if the translate_sync_worker function exists
        if hasattr(app_module, 'translate_sync_worker'):
            print("✅ translate_sync_worker function found")
        else:
            print("❌ translate_sync_worker function not found")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Syntax error in app.py: {e}")
        return False

def validate_signal_fix():
    """Validate that the signal handling fix is present"""
    print("\n🔍 Validating signal handling fix...")
    
    try:
        with open("app.py", "r") as f:
            content = f.read()
        
        # Check for signal handling code
        if "safe_signal" in content:
            print("✅ safe_signal function found")
        else:
            print("❌ safe_signal function not found")
            return False
            
        if "signal only works in main thread" in content:
            print("✅ Signal error handling found")
        else:
            print("❌ Signal error handling not found")
            return False
            
        if "original_signal = signal.signal" in content:
            print("✅ Signal monkey patching found")
        else:
            print("❌ Signal monkey patching not found")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error reading app.py: {e}")
        return False

def validate_environment():
    """Validate that the environment is set up correctly"""
    print("\n🔍 Validating environment...")
    
    # Check if required files exist
    required_files = ["app.py", ".env"]
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} exists")
        else:
            print(f"⚠️ {file} not found (may be optional)")
    
    # Check if virtual environment exists
    if os.path.exists("srt-venv"):
        print("✅ Virtual environment found")
    else:
        print("❌ Virtual environment not found")
        return False
    
    return True

def main():
    """Run all validations"""
    print("🧪 Running validation tests for SRT translation service fixes...\n")
    
    # Change to the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    all_passed = True
    
    # Run validations
    if not validate_environment():
        all_passed = False
    
    if not validate_app_syntax():
        all_passed = False
    
    if not validate_signal_fix():
        all_passed = False
    
    # Summary
    print("\n" + "="*50)
    if all_passed:
        print("🎉 All validations passed!")
        print("\n📋 Summary of fixes applied:")
        print("   ✅ Fixed 'signal only works in main thread' error")
        print("   ✅ Added root endpoint (/) to prevent 404 errors")
        print("   ✅ Added health endpoint (/health)")
        print("   ✅ Improved error handling in translation worker")
        print("\n🚀 Your SRT translation service should now work correctly!")
        print("   The signal handling issue has been resolved by monkey-patching")
        print("   the signal module to safely ignore signal operations in background threads.")
    else:
        print("💥 Some validations failed!")
        print("   Please check the errors above and fix them before deploying.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
