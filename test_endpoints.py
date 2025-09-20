#!/usr/bin/env python3
"""
Test script to verify that the API endpoints work correctly.
"""

import os
import sys
import requests
import time
import subprocess
import signal
from threading import Thread

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_endpoints():
    """Test the API endpoints"""
    print("🧪 Testing API endpoints...")
    
    # Start the server in a subprocess
    server_process = None
    try:
        print("🚀 Starting test server...")
        server_process = subprocess.Popen(
            ["python", "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8001"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for server to start
        time.sleep(3)
        
        base_url = "http://127.0.0.1:8001"
        
        # Test root endpoint
        print("📍 Testing root endpoint (/)...")
        try:
            response = requests.get(f"{base_url}/", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Root endpoint works: {data['message']}")
                print(f"   Status: {data['status']}")
                print(f"   Supported languages: {data['supported_languages']}")
            else:
                print(f"❌ Root endpoint failed with status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Root endpoint error: {e}")
            return False
        
        # Test health endpoint
        print("📍 Testing health endpoint (/health)...")
        try:
            response = requests.get(f"{base_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health endpoint works: {data['status']}")
            else:
                print(f"❌ Health endpoint failed with status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health endpoint error: {e}")
            return False
        
        print("\n🎉 All endpoint tests passed!")
        return True
        
    except Exception as e:
        print(f"💥 Server startup error: {e}")
        return False
    
    finally:
        # Clean up server process
        if server_process:
            print("🛑 Stopping test server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()

if __name__ == "__main__":
    success = test_endpoints()
    sys.exit(0 if success else 1)
