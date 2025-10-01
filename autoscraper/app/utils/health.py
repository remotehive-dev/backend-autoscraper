#!/usr/bin/env python3
"""
Health Check Utilities
Enterprise-grade health monitoring for autoscraper service
"""

import time
import psutil
import redis
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel
from loguru import logger

from app.database.database import DatabaseManager
from config.settings import get_settings

settings = get_settings()


class HealthStatus(BaseModel):
    """Health status model"""
    status: str
    timestamp: datetime
    version: str = "1.0.0"
    environment: str
    uptime_seconds: float
    checks: Dict[str, Any]


class LivenessResponse(BaseModel):
    """Liveness probe response"""
    status: str = "alive"
    timestamp: datetime


class ReadinessResponse(BaseModel):
    """Readiness probe response"""
    status: str
    timestamp: datetime
    ready: bool
    checks: Dict[str, bool]


class HealthChecker:
    """Health check implementation"""
    
    def __init__(self):
        self.start_time = time.time()
        self.redis_client = None
        
        # Initialize Redis client for health checks
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=2,
                socket_timeout=2
            )
        except Exception as e:
            logger.warning(f"Redis client initialization failed: {e}")
    
    def get_uptime(self) -> float:
        """Get service uptime in seconds"""
        return time.time() - self.start_time
    
    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity"""
        try:
            start_time = time.time()
            db_manager = DatabaseManager()
            await db_manager.initialize()
            
            # Use MongoDB health check method
            health_result = await db_manager.health_check()
            
            response_time = (time.time() - start_time) * 1000  # ms
            
            if health_result.get("status") == "healthy":
                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time, 2),
                    "database_type": health_result.get("database_type", "mongodb"),
                    "database_name": health_result.get("database_name")
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": health_result.get("error", "Unknown database error"),
                    "database_type": health_result.get("database_type", "mongodb")
                }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity"""
        if not self.redis_client:
            return {
                "status": "unavailable",
                "error": "Redis client not initialized"
            }
        
        try:
            start_time = time.time()
            self.redis_client.ping()
            response_time = (time.time() - start_time) * 1000  # ms
            
            # Get Redis info
            info = self.redis_client.info()
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "redis_version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human")
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def check_celery(self) -> Dict[str, Any]:
        """Check Celery worker status"""
        try:
            from celery import Celery
            
            # Create Celery app for inspection
            celery_app = Celery(
                'autoscraper',
                broker=settings.CELERY_BROKER_URL,
                backend=settings.CELERY_RESULT_BACKEND
            )
            
            # Get active workers
            inspect = celery_app.control.inspect()
            active_workers = inspect.active()
            
            if active_workers:
                worker_count = len(active_workers)
                return {
                    "status": "healthy",
                    "active_workers": worker_count,
                    "workers": list(active_workers.keys())
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": "No active Celery workers found"
                }
        except Exception as e:
            logger.error(f"Celery health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Load average (Unix-like systems)
            load_avg = None
            try:
                load_avg = psutil.getloadavg()
            except AttributeError:
                # Windows doesn't have load average
                pass
            
            return {
                "status": "healthy",
                "cpu_percent": cpu_percent,
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "percent_used": memory.percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent_used": round((disk.used / disk.total) * 100, 2)
                },
                "load_average": load_avg
            }
        except Exception as e:
            logger.error(f"System resource check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def check_main_service(self) -> Dict[str, Any]:
        """Check main RemoteHive service connectivity"""
        try:
            import httpx
            
            url = f"{settings.MAIN_SERVICE_URL}{settings.MAIN_SERVICE_HEALTH_ENDPOINT}"
            
            with httpx.Client(timeout=5.0) as client:
                start_time = time.time()
                response = client.get(url)
                response_time = (time.time() - start_time) * 1000  # ms
                
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "response_time_ms": round(response_time, 2),
                        "main_service_status": response.status_code
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "error": f"Main service returned status {response.status_code}"
                    }
        except Exception as e:
            logger.error(f"Main service health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def get_comprehensive_health(self) -> HealthStatus:
        """Get comprehensive health status"""
        checks = {
            "database": await self.check_database(),
            "redis": self.check_redis(),
            "celery": self.check_celery(),
            "system_resources": self.check_system_resources(),
            "main_service": self.check_main_service()
        }
        
        # Determine overall status
        unhealthy_checks = [
            name for name, check in checks.items() 
            if check.get("status") == "unhealthy"
        ]
        
        overall_status = "unhealthy" if unhealthy_checks else "healthy"
        
        return HealthStatus(
            status=overall_status,
            timestamp=datetime.utcnow(),
            environment=settings.ENVIRONMENT,
            uptime_seconds=self.get_uptime(),
            checks=checks
        )
    
    async def get_readiness(self) -> ReadinessResponse:
        """Get readiness status (for Kubernetes readiness probe)"""
        db_check = await self.check_database()
        redis_check = self.check_redis()
        
        checks = {
            "database": db_check.get("status") == "healthy",
            "redis": redis_check.get("status") == "healthy"
        }
        
        ready = all(checks.values())
        status = "ready" if ready else "not_ready"
        
        return ReadinessResponse(
            status=status,
            timestamp=datetime.utcnow(),
            ready=ready,
            checks=checks
        )


# Create health checker instance
health_checker = HealthChecker()

# Create router
health_router = APIRouter()


@health_router.get("/", response_model=HealthStatus)
async def health_check():
    """Comprehensive health check endpoint"""
    return await health_checker.get_comprehensive_health()


@health_router.get("/live", response_model=LivenessResponse)
async def liveness_probe():
    """Liveness probe endpoint (for Kubernetes)"""
    return LivenessResponse(
        timestamp=datetime.utcnow()
    )


@health_router.get("/ready", response_model=ReadinessResponse)
async def readiness_probe():
    """Readiness probe endpoint (for Kubernetes)"""
    return await health_checker.get_readiness()


@health_router.get("/database")
async def database_health():
    """Database-specific health check"""
    return await health_checker.check_database()


@health_router.get("/redis")
async def redis_health():
    """Redis-specific health check"""
    return health_checker.check_redis()


@health_router.get("/celery")
async def celery_health():
    """Celery-specific health check"""
    return health_checker.check_celery()


@health_router.get("/system")
async def system_health():
    """System resources health check"""
    return health_checker.check_system_resources()