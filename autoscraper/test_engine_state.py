#!/usr/bin/env python3
"""
Test script to verify the Pydantic validation fix for engine state endpoint
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.mongodb_models import EngineStatus, EngineState
from app.schemas import EngineStateResponse
from pydantic import ValidationError
import json

def test_engine_status_enum():
    """Test that EngineStatus enum works correctly"""
    print("Testing EngineStatus enum...")
    
    # Test enum values
    print(f"EngineStatus.IDLE = {EngineStatus.IDLE}")
    print(f"EngineStatus.RUNNING = {EngineStatus.RUNNING}")
    print(f"EngineStatus.PAUSED = {EngineStatus.PAUSED}")
    print(f"EngineStatus.ERROR = {EngineStatus.ERROR}")
    
    return True

def test_engine_state_creation():
    """Test creating EngineState with enum value"""
    print("\nTesting EngineState creation...")
    
    try:
        from datetime import datetime
        # Test with minimal fields (all have defaults)
        engine_state = EngineState()
        print(f"✅ EngineState created successfully with status: {engine_state.status}")
        
        # Test with explicit enum value
        engine_state2 = EngineState(status=EngineStatus.RUNNING)
        print(f"✅ EngineState with explicit enum created: {engine_state2.status}")
        
        return True
    except Exception as e:
        import traceback
        print(f"❌ Failed to create EngineState: {e}")
        print(f"Full traceback: {traceback.format_exc()}")
        return False

def test_engine_state_response():
    """Test EngineStateResponse schema validation"""
    print("\nTesting EngineStateResponse schema...")
    
    try:
        from datetime import datetime
        # Test with enum value - using correct schema fields
        response_data = {
            "status": EngineStatus.IDLE,
            "active_jobs": 0,
            "queued_jobs": 0,
            "total_jobs_today": 0,
            "success_rate": 0.0,
            "last_activity": datetime.utcnow(),
            "uptime_seconds": 0
        }
        
        response = EngineStateResponse(**response_data)
        print(f"✅ EngineStateResponse created successfully with status: {response.status}")
        
        # Test JSON serialization
        json_data = response.model_dump()
        print(f"✅ JSON serialization successful: {json_data['status']}")
        
        return True
    except ValidationError as e:
        print(f"❌ Pydantic validation error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_string_vs_enum():
    """Test the difference between string and enum usage"""
    print("\nTesting string vs enum usage...")
    
    try:
        from datetime import datetime
        current_time = datetime.utcnow()
        
        # Test with string (old way - should still work)
        response_with_string = EngineStateResponse(
            status="idle",
            active_jobs=0,
            queued_jobs=0,
            total_jobs_today=0,
            success_rate=0.0,
            last_activity=current_time,
            uptime_seconds=0
        )
        print(f"✅ String status works: {response_with_string.status}")
        
        # Test with enum (new way - should work)
        response_with_enum = EngineStateResponse(
            status=EngineStatus.IDLE,
            active_jobs=0,
            queued_jobs=0,
            total_jobs_today=0,
            success_rate=0.0,
            last_activity=current_time,
            uptime_seconds=0
        )
        print(f"✅ Enum status works: {response_with_enum.status}")
        
        return True
    except Exception as e:
        print(f"❌ Error in string vs enum test: {e}")
        return False

if __name__ == "__main__":
    print("=== Engine State Pydantic Validation Test ===")
    
    tests = [
        test_engine_status_enum,
        test_engine_state_creation,
        test_engine_state_response,
        test_string_vs_enum
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! The Pydantic validation fix is working correctly.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. There may still be issues with the Pydantic validation.")
        sys.exit(1)