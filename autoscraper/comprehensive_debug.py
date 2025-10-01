#!/usr/bin/env python3
"""
Comprehensive debug to find the exact difference between working and non-working approaches
"""

import asyncio
import sys
import os
from motor.motor_asyncio import AsyncIOMotorClient

# Add the service directory to Python path
sys.path.append('/Users/ranjeettiwary/Downloads/developer/RemoteHive_Migration_Package/autoscraper-service')

async def test_all_approaches():
    """Test all different approaches to identify the issue"""
    
    print("=== COMPREHENSIVE DEBUG TEST ===")
    print()
    
    # 1. Direct PyMongo connection (known working)
    print("1. DIRECT PYMONGO CONNECTION:")
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb+srv://remotehiveofficial_db_user:b9z6QbkaiR3qc2KZ@remotehive.l5zq7k0.mongodb.net/?retryWrites=true&w=majority&appName=Remotehive")
        db = client.remotehive_autoscraper
        count = db.job_boards.count_documents({})
        print(f"   ✓ PyMongo count: {count}")
        client.close()
    except Exception as e:
        print(f"   ✗ PyMongo failed: {e}")
    
    # 2. Motor async connection (known working)
    print("\n2. MOTOR ASYNC CONNECTION:")
    try:
        client = AsyncIOMotorClient("mongodb+srv://remotehiveofficial_db_user:b9z6QbkaiR3qc2KZ@remotehive.l5zq7k0.mongodb.net/?retryWrites=true&w=majority&appName=Remotehive")
        db = client.remotehive_autoscraper
        count = await db.job_boards.count_documents({})
        print(f"   ✓ Motor count: {count}")
        client.close()
    except Exception as e:
        print(f"   ✗ Motor failed: {e}")
    
    # 3. Service manager approach (working in debug_service_vs_direct.py)
    print("\n3. SERVICE MANAGER APPROACH (debug_service_vs_direct.py style):")
    try:
        from app.database.mongodb_manager import get_autoscraper_mongodb_manager
        manager = await get_autoscraper_mongodb_manager()
        print(f"   ✓ Manager connected: {manager.is_connected}")
        
        service_db = manager.get_database()
        print(f"   ✓ Database name: {service_db.name}")
        
        service_collection = service_db.job_boards
        service_direct_count = await service_collection.count_documents({})
        print(f"   ✓ Service direct count: {service_direct_count}")
        
        # Test Beanie in this context
        from app.models.mongodb_models import JobBoard
        beanie_count = await JobBoard.count()
        print(f"   ✓ Beanie count in this context: {beanie_count}")
        
    except Exception as e:
        print(f"   ✗ Service manager failed: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. Fresh import approach (test_beanie_in_service.py style)
    print("\n4. FRESH IMPORT APPROACH (test_beanie_in_service.py style):")
    try:
        # Clear any cached imports
        modules_to_clear = []
        for module_name in sys.modules.keys():
            if module_name.startswith('app.'):
                modules_to_clear.append(module_name)
        
        for module_name in modules_to_clear:
            if module_name in sys.modules:
                del sys.modules[module_name]
        
        # Fresh imports
        from app.models.mongodb_models import JobBoard
        from app.database.mongodb_manager import get_autoscraper_mongodb_manager
        
        mongodb_manager = await get_autoscraper_mongodb_manager()
        print(f"   ✓ Fresh manager connected: {mongodb_manager.is_connected}")
        
        # Test Beanie with fresh imports
        fresh_count = await JobBoard.count()
        print(f"   ✓ Fresh Beanie count: {fresh_count}")
        
        # Test direct collection access
        db = mongodb_manager.get_database()
        direct_count = await db.job_boards.count_documents({})
        print(f"   ✓ Fresh direct count: {direct_count}")
        
    except Exception as e:
        print(f"   ✗ Fresh import failed: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. Check Beanie initialization state
    print("\n5. BEANIE INITIALIZATION STATE:")
    try:
        from app.models.mongodb_models import JobBoard
        import beanie
        
        print(f"   ✓ JobBoard class: {JobBoard}")
        print(f"   ✓ JobBoard.__bases__: {JobBoard.__bases__}")
        
        # Check if Beanie is initialized
        if hasattr(JobBoard, 'get_motor_collection'):
            collection = JobBoard.get_motor_collection()
            print(f"   ✓ Motor collection: {collection}")
            print(f"   ✓ Collection name: {collection.name}")
            print(f"   ✓ Collection database: {collection.database.name}")
            
            # Check collection stats
            collection_count = await collection.count_documents({})
            print(f"   ✓ Collection count via motor: {collection_count}")
        else:
            print(f"   ✗ JobBoard not properly initialized")
            
    except Exception as e:
        print(f"   ✗ Beanie state check failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== DEBUG COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(test_all_approaches())