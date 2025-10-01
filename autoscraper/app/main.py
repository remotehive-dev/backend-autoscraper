#!/usr/bin/env python3
"""
RemoteHive AutoScraper Service
Enterprise-grade dedicated autoscraper API server
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import uvicorn

# Note: Using relative imports within autoscraper service only

from config.settings import get_settings
from app.middleware.auth import AuthMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
# from app.utils.metrics import MetricsMiddleware
from app.database.database import DatabaseManager
from app.database.mongodb_manager import init_autoscraper_mongodb, close_autoscraper_mongodb
from app.api.autoscraper import router as autoscraper_router
from app.api import ai, monitoring, scraping
from app.utils.health import health_router
from debug_endpoint import router as debug_router
# from app.utils.metrics import metrics_router

settings = get_settings()

# Global database manager instance
db_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global db_manager
    
    # Startup
    logger.info("Starting RemoteHive AutoScraper Service with MongoDB Atlas...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Host: {settings.HOST}:{settings.PORT}")
    
    try:
        # Initialize MongoDB Atlas connection
        db_manager = DatabaseManager()
        await db_manager.initialize()
        
        # Store in app state for access in routes
        app.state.db_manager = db_manager
        
        logger.info("MongoDB Atlas initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to start AutoScraper Service: {str(e)}")
        raise
    
    # Application is running
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down AutoScraper Service...")
    # Note: We don't close the MongoDB connection here as it's shared globally
    # The connection will be closed when the process terminates
    
    logger.info("AutoScraper Service shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="RemoteHive AutoScraper Service",
    description="Enterprise-grade job scraping and normalization service",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
    lifespan=lifespan
)

# Add trusted host middleware for production
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS
    )

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Add custom middleware (order matters)
# app.add_middleware(MetricsMiddleware)  # Temporarily disabled
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "type": "http_error"
            },
            "request_id": getattr(request.state, 'request_id', None)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error" if not settings.DEBUG else str(exc),
                "type": "internal_error"
            },
            "request_id": getattr(request.state, 'request_id', None)
        }
    )


# Include routers
app.include_router(health_router, prefix="/health", tags=["Health"])
# app.include_router(metrics_router, prefix="/metrics", tags=["Metrics"])  # Temporarily disabled
app.include_router(autoscraper_router, tags=["AutoScraper"])
app.include_router(debug_router, tags=["Debug"])
app.include_router(ai.router)
app.include_router(monitoring.router)
app.include_router(scraping.router)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "service": "RemoteHive AutoScraper Service",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs" if settings.DEBUG else "disabled"
    }


@app.get("/info", tags=["Root"])
async def info():
    """Service information endpoint"""
    return {
        "service": "RemoteHive AutoScraper Service",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "database_url": settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else "configured",
        "redis_url": settings.REDIS_URL.split('@')[-1] if '@' in settings.REDIS_URL else "configured",
        "features": {
            "authentication": True,
            "rate_limiting": True,
            "metrics": True,
            "health_checks": True,
            "job_scraping": True,
            "job_normalization": True
        }
    }


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO" if settings.ENVIRONMENT != "development" else "DEBUG"
    )
    
    # Add file logging if log file is configured
    if settings.LOG_FILE:
        # Ensure logs directory exists
        log_path = Path(settings.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            settings.LOG_FILE,
            rotation="10 MB",
            retention="30 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="INFO"
        )
    
    logger.info(f"Starting AutoScraper Service on {settings.HOST}:{settings.PORT}")
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        workers=1 if settings.ENVIRONMENT == "development" else settings.WORKERS,
        log_level="info" if settings.ENVIRONMENT != "development" else "debug"
    )