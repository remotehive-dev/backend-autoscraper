#!/usr/bin/env python3
"""
Test script for CSV upload with new field mapping
"""

import sys
from pathlib import Path
import requests

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.utils.jwt_auth import create_access_token

def test_csv_upload():
    """Test the CSV upload endpoint with new field mapping"""
    try:
        # Create a test access token
        token = create_access_token("test_user", {"role": "admin"})
        print(f"Generated token: {token[:50]}...")
        
        # Test the CSV upload endpoint
        url = "http://localhost:8001/api/v1/autoscraper/job-boards/upload-csv"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        # Read the test CSV file
        csv_file_path = "test_upload.csv"
        with open(csv_file_path, 'rb') as f:
            files = {'file': ('test_upload.csv', f, 'text/csv')}
            
            print(f"Testing endpoint: {url}")
            print(f"Uploading file: {csv_file_path}")
            
            response = requests.post(url, headers=headers, files=files)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ CSV upload test PASSED!")
            
            # Parse response to check results
            try:
                result = response.json()
                print(f"Created: {result.get('created', 0)} job boards")
                print(f"Updated: {result.get('updated', 0)} job boards")
                print(f"Total processed: {result.get('total_processed', 0)} records")
            except:
                pass
        else:
            print(f"\n❌ CSV upload test FAILED!")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_csv_upload()