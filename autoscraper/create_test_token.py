#!/usr/bin/env python3
"""
Create a test JWT token for autoscraper service authentication
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.utils.jwt_auth import JWTManager
from config.settings import get_settings

def create_test_token():
    """Create a test admin token"""
    try:
        # Initialize JWT manager
        jwt_manager = JWTManager()
        
        # Create an admin access token
        token = jwt_manager.create_access_token(
            subject="admin@remotehive.in",
            user_data={
                "email": "admin@remotehive.in",
                "role": "admin",
                "roles": ["admin", "user"],
                "permissions": ["scrape", "admin", "read", "write", "delete"]
            }
        )
        
        print(f"Test Admin Token: {token}")
        print("\nUse this token in Authorization header:")
        print(f"Authorization: Bearer {token}")
        
        return token
        
    except Exception as e:
        print(f"Error creating token: {e}")
        return None

if __name__ == "__main__":
    create_test_token()