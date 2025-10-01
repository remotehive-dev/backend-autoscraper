from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
import psutil
import time

from backend.core.database import get_db
from backend.database.database import MongoDBManager
from backend.core.config import settings

router = APIRouter()

# Database manager will be initialized when needed
db_manager = None

async def get_db_manager():
    global db_manager
    if db_manager is None:
        db_manager = MongoDBManager()
        # Initialize the connection with settings
        await db_manager.connect(
            connection_string=settings.MONGODB_URL,
            database_name=settings.MONGODB_DATABASE_NAME
        )
    return db_manager

@router.get("/", response_model=Dict[str, Any])
async def health_check():
    """
    Basic health check endpoint
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "RemoteHive API",
        "version": "1.0.0"
    }

@router.get("/detailed", response_model=Dict[str, Any])
async def detailed_health_check(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Detailed health check with database and system metrics
    """
    try:
        # Database health check
        db_mgr = get_db_manager()
        db_health = db_mgr.health_check()
        
        # System metrics
        system_metrics = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent if hasattr(psutil.disk_usage('/'), 'percent') else 0,
            "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
        }
        
        # Database performance metrics
        db_metrics = db_mgr.get_metrics()
        
        return {
            "status": "healthy" if db_health["status"] == "healthy" else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "database": db_health,
            "system": system_metrics,
            "performance": db_metrics,
            "uptime_seconds": (datetime.utcnow() - db_mgr._metrics['uptime_start']).total_seconds()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )

@router.get("/database", response_model=Dict[str, Any])
async def database_health_check():
    """
    Database-specific health check with connection pool metrics
    """
    try:
        db_mgr = await get_db_manager()
        health_result = await db_mgr.health_check()
        connection_info = db_mgr.get_connection_info()
        
        return {
            "status": health_result["status"],
            "timestamp": datetime.utcnow().isoformat(),
            "database_type": health_result.get("database_type", "unknown"),
            "connection_pool": health_result.get("pool_status", {}),
            "connection_info": connection_info,
            "response_time_ms": health_result.get("response_time_ms", 0)
        }
        
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unhealthy: {str(e)}"
        )

@router.get("/metrics", response_model=Dict[str, Any])
async def performance_metrics():
    """
    Performance metrics endpoint for monitoring
    """
    try:
        db_mgr = get_db_manager()
        metrics = db_mgr.get_metrics()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": metrics,
            "uptime_seconds": (datetime.utcnow() - db_mgr._metrics['uptime_start']).total_seconds()
        }
        
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metrics: {str(e)}"
        )

@router.post("/maintenance", response_model=Dict[str, Any])
async def run_maintenance():
    """
    Run database maintenance tasks
    """
    try:
        db_mgr = get_db_manager()
        maintenance_result = db_mgr.execute_maintenance()
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "maintenance_tasks": maintenance_result
        }
        
    except Exception as e:
        logger.error(f"Maintenance failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Maintenance failed: {str(e)}"
        )

@router.post("/reset-metrics", response_model=Dict[str, Any])
async def reset_performance_metrics():
    """
    Reset performance metrics counters
    """
    try:
        db_mgr = get_db_manager()
        db_mgr.reset_metrics()
        
        return {
            "status": "reset",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Performance metrics have been reset"
        }
        
    except Exception as e:
        logger.error(f"Failed to reset metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset metrics: {str(e)}"
        )

@router.get("/readiness", response_model=Dict[str, Any])
async def readiness_check(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Kubernetes-style readiness probe
    """
    try:
        # Quick database connectivity test
        start_time = time.time()
        db.execute("SELECT 1")
        response_time = (time.time() - start_time) * 1000
        
        if response_time > 5000:  # 5 seconds threshold
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database response time too slow"
            )
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat(),
            "response_time_ms": response_time
        }
        
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )

@router.get("/liveness", response_model=Dict[str, Any])
async def liveness_check():
    """
    Kubernetes-style liveness probe
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": (datetime.utcnow() - get_db_manager()._metrics['uptime_start']).total_seconds()
    }