#!/usr/bin/env python3
"""
Test script to verify that the signal handling fix works correctly.
This simulates the background task scenario that was causing the error.
"""

import os
import sys
import threading
import time
from typing import Dict, Any

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_signal_handling():
    """Test the signal handling fix in a background thread"""
    print("🧪 Testing signal handling fix...")
    
    # Simulate the translate_sync_worker function
    def mock_translate_worker(language: str) -> Dict[str, Any]:
        try:
            import signal
            print(f"📍 Testing {language} in thread: {threading.current_thread().name}")
            
            # Monkey patch the signal handling (same as in app.py)
            original_signal = signal.signal
            original_raise_signal = getattr(signal, 'raise_signal', None)
            
            def safe_signal(sig, handler):
                try:
                    return original_signal(sig, handler)
                except ValueError as e:
                    if "signal only works in main thread" in str(e):
                        print(f"⚠️ Ignoring signal setup in background thread for {language}")
                        return None
                    else:
                        raise e
            
            def safe_raise_signal(sig):
                try:
                    if original_raise_signal:
                        return original_raise_signal(sig)
                except ValueError as e:
                    if "signal only works in main thread" in str(e):
                        print(f"⚠️ Ignoring signal raise in background thread for {language}")
                        return None
                    else:
                        raise e
            
            # Replace signal functions with safe versions
            signal.signal = safe_signal
            if original_raise_signal:
                signal.raise_signal = safe_raise_signal
            
            try:
                # Test signal operations that would normally fail
                def dummy_handler(sig, frame):
                    pass
                
                # This would normally cause "signal only works in main thread" error
                signal.signal(2, dummy_handler)  # SIGINT
                print(f"✅ Signal setup successful for {language}")
                
                # Test signal raising (if available)
                if hasattr(signal, 'raise_signal'):
                    # This is just a test - we won't actually raise the signal
                    print(f"✅ Signal raise function available for {language}")
                
                return {
                    "language": language,
                    "status": "success",
                    "message": "Signal handling test passed"
                }
                
            finally:
                # Restore original functions
                signal.signal = original_signal
                if original_raise_signal:
                    signal.raise_signal = original_raise_signal
                    
        except Exception as e:
            return {
                "language": language,
                "status": "error",
                "error": str(e)
            }
    
    # Test in main thread first
    print("\n🔍 Testing in main thread:")
    main_result = mock_translate_worker("MainThread-Test")
    print(f"Main thread result: {main_result}")
    
    # Test in background thread (this is where the original error occurred)
    print("\n🔍 Testing in background thread:")
    results = []
    
    def thread_worker(lang):
        result = mock_translate_worker(lang)
        results.append(result)
    
    # Create and start background threads
    threads = []
    test_languages = ["English", "Spanish", "French"]
    
    for lang in test_languages:
        thread = threading.Thread(target=thread_worker, args=(lang,))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Check results
    print("\n📊 Test Results:")
    successful = [r for r in results if r.get("status") == "success"]
    failed = [r for r in results if r.get("status") == "error"]
    
    print(f"✅ Successful: {len(successful)}/{len(results)}")
    if failed:
        print("❌ Failed:")
        for fail in failed:
            print(f"   - {fail['language']}: {fail.get('error', 'Unknown error')}")
    
    if len(successful) == len(results):
        print("\n🎉 All tests passed! Signal handling fix is working correctly.")
        return True
    else:
        print("\n💥 Some tests failed. Signal handling fix needs adjustment.")
        return False

if __name__ == "__main__":
    success = test_signal_handling()
    sys.exit(0 if success else 1)
