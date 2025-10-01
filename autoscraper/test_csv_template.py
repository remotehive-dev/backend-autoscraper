#!/usr/bin/env python3
"""
Test script for CSV template download endpoint
"""

import sys
from pathlib import Path
import requests

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.utils.jwt_auth import create_access_token

def test_csv_template_download():
    """Test the CSV template download endpoint"""
    try:
        # Create a test access token
        token = create_access_token("test_user", {"role": "admin"})
        print(f"Generated token: {token[:50]}...")
        
        # Test the CSV template endpoint
        url = "http://localhost:8001/api/v1/autoscraper/job-boards/csv-template"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        print(f"Testing endpoint: {url}")
        response = requests.get(url, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("\nCSV Template Content:")
            print(response.text)
            print("\n✅ CSV template download test PASSED!")
        else:
            print(f"\n❌ CSV template download test FAILED!")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_csv_template_download()