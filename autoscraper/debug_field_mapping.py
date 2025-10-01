#!/usr/bin/env python3
"""
Debug script to compare JobBoard model fields with actual database documents
"""

import asyncio
import sys
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from config.settings import get_settings

async def debug_field_mapping():
    """
    Compare JobBoard model fields with actual database documents
    """
    try:
        print("=== Field Mapping Debug ===")
        
        # Get settings
        settings = get_settings()
        print(f"1. Connecting to: {settings.MONGODB_DATABASE_NAME}")
        
        # Connect to MongoDB directly
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        db = client[settings.MONGODB_DATABASE_NAME]
        
        # Test connection
        await client.admin.command('ping')
        print("   ✓ MongoDB connection successful")
        
        # Get job_boards collection
        job_boards_collection = db.job_boards
        
        # Get a sample document
        print(f"\n2. Analyzing document structure:")
        sample_doc = await job_boards_collection.find_one({})
        
        if sample_doc:
            print(f"   Sample document fields:")
            for key, value in sample_doc.items():
                value_type = type(value).__name__
                if isinstance(value, str) and len(value) > 50:
                    value_preview = f"{value[:50]}..."
                else:
                    value_preview = str(value)
                print(f"     - {key}: {value_type} = {value_preview}")
        else:
            print("   No documents found")
            return
        
        # Check for required fields that might be missing
        print(f"\n3. Checking required JobBoard model fields:")
        required_fields = [
            'name', 'type', 'base_url', 'search_url_template', 
            'is_active', 'rate_limit_delay', 'max_pages_per_search',
            'selectors', 'headers', 'cookies', 'created_at', 'updated_at'
        ]
        
        missing_fields = []
        for field in required_fields:
            if field in sample_doc:
                print(f"     ✓ {field}: {type(sample_doc[field]).__name__}")
            else:
                print(f"     ✗ {field}: MISSING")
                missing_fields.append(field)
        
        if missing_fields:
            print(f"\n   Missing fields: {missing_fields}")
        else:
            print(f"\n   All required fields present")
        
        # Check for field name variations
        print(f"\n4. Checking for field name variations:")
        field_variations = {
            'base_url': ['url', 'website', 'site_url'],
            'search_url_template': ['search_url', 'search_template'],
            'is_active': ['active', 'enabled', 'status']
        }
        
        for model_field, variations in field_variations.items():
            if model_field not in sample_doc:
                for variation in variations:
                    if variation in sample_doc:
                        print(f"     Found variation: {model_field} -> {variation}")
                        break
        
        # Test a simple query using the actual field names
        print(f"\n5. Testing query with actual field names:")
        
        # Try different field name combinations
        test_queries = [
            {'is_active': True},
            {'active': True},
            {'status': 'active'},
            {}
        ]
        
        for i, query in enumerate(test_queries):
            try:
                count = await job_boards_collection.count_documents(query)
                print(f"     Query {i+1} {query}: {count} documents")
            except Exception as e:
                print(f"     Query {i+1} {query}: ERROR - {e}")
        
        print(f"\n=== Debug Complete ===")
        
    except Exception as e:
        print(f"Error during debug: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Close connection
        if 'client' in locals():
            client.close()
            print("MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(debug_field_mapping())