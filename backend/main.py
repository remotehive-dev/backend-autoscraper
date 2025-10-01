from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from loguru import logger
import logging
from backend.database import init_database
from backend.api.v1 import api_router
from backend.api.v1.endpoints import auth_endpoints, oauth
from backend.api.employers import router as employers_router
from backend.core.config import settings
from backend.core.logging import setup_logging, get_logger
from backend.core.monitoring import app_monitor
from backend.scraper.config import get_scraping_config, set_scraping_config, EnhancedScrapingConfig
from backend.middleware.error_handler import (
    ErrorHandlingMiddleware,
    HealthCheckMiddleware,
    validation_exception_handler,
    http_exception_handler
)
from backend.middleware.security import SecurityMiddleware, CSRFProtectionMiddleware
from backend.middleware.validation import ValidationMiddleware
from backend.middleware.enhanced_middleware import EnhancedMiddleware
from backend.middleware.rate_limiting import RateLimitingMiddleware
from backend.api.versioning import VersionRegistry, add_version_headers
from backend.api.documentation import APIDocumentation
from backend.api.integration import setup_enhanced_api

# Setup centralized logging
setup_logging()
app_logger = get_logger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    app_logger.info("Starting up RemoteHive API...")
    try:
        # Initialize MongoDB database with enhanced error handling
        await init_database()
        app_logger.info("MongoDB database initialized successfully")
        
        # Verify Beanie initialization by testing User model
        from backend.models.mongodb_models import User
        try:
            user_count = await User.count()
            app_logger.info(f"Beanie verification successful: {user_count} users found")
        except Exception as e:
            app_logger.error(f"Beanie verification failed: {e}")
            # Force re-initialization if Beanie is not working
            from backend.database.mongodb_manager import init_mongodb
            await init_mongodb()
            user_count = await User.count()
            app_logger.info(f"Beanie re-initialization successful: {user_count} users found")
        
        # Create default admin user
        from backend.core.database import create_default_data
        await create_default_data()
        app_logger.info("Default admin user created successfully")
        
        # Initialize enhanced scraping configuration
        scraping_config = EnhancedScrapingConfig.from_env()
        set_scraping_config(scraping_config)
        app_logger.info(f"Enhanced scraping engine initialized in {scraping_config.scraping_mode.value} mode")
        
        # Start monitoring systems (temporarily disabled for debugging)
        # await app_monitor.start()
        app_logger.info("Monitoring systems startup skipped for debugging")
        
    except Exception as e:
        app_logger.error(f"Failed to initialize application: {e}")
        raise
    
    app_logger.info("RemoteHive API started successfully")
    yield
    
    app_logger.info("Shutting down RemoteHive API...")
    try:
        # Stop monitoring systems (temporarily disabled for debugging)
        # await app_monitor.stop()
        app_logger.info("Monitoring systems shutdown skipped for debugging")
    except Exception as e:
        app_logger.error(f"Error during shutdown: {e}")

# Create FastAPI instance with disabled default docs
app = FastAPI(
    title="RemoteHive API",
    description="A comprehensive job board platform for remote work opportunities with enhanced API design",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None,  # Disable default docs
    redoc_url=None  # Disable default redoc
)

# Add basic middleware (order matters - add from innermost to outermost)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(HealthCheckMiddleware)
# app.add_middleware(ValidationMiddleware)  # Temporarily disabled - ValidationMiddleware calls await request.body() which conflicts with FastAPI
app.add_middleware(SecurityMiddleware)
app.add_middleware(CSRFProtectionMiddleware)
app.add_middleware(RateLimitingMiddleware, enable_rate_limiting=settings.RATE_LIMIT_ENABLED)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for Swagger UI
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    app_logger.warning(f"Could not mount static files: {e}")

# Setup enhanced API integration (includes validation, versioning, documentation, etc.)
# api_integration = setup_enhanced_api(app)  # Temporarily disabled - contains middleware that calls await request.body()

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Add compatibility router for tests that expect /api prefix
compat_router = APIRouter()
compat_router.include_router(auth_endpoints.router, prefix="/auth", tags=["authentication-compat"])
compat_router.include_router(oauth.router, prefix="/auth", tags=["oauth-compat"])
app.include_router(compat_router, prefix="/api")

# Custom docs endpoint with local Swagger UI assets
@app.get("/docs", response_class=HTMLResponse)
async def custom_swagger_ui_html():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>RemoteHive API Documentation</title>
        <link rel="stylesheet" type="text/css" href="/static/swagger-ui/swagger-ui.css" />
        <style>
            html { box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }
            *, *:before, *:after { box-sizing: inherit; }
            body { margin:0; background: #fafafa; }
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="/static/swagger-ui/swagger-ui-bundle.js"></script>
        <script>
            const ui = SwaggerUIBundle({
                url: '/openapi.json',
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.presets.standalone
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "BaseLayout",
                tryItOutEnabled: true,
                displayRequestDuration: true,
                filter: true,
                showExtensions: true,
                showCommonExtensions: true
            });
        </script>
    </body>
    </html>
    """

# Include direct API routes for admin panel compatibility
app.include_router(employers_router, prefix="/api/employers")



# Register exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

@app.get("/")
async def root():
    """Root endpoint"""
    app_logger.info("Root endpoint accessed")
    return {
        "message": "Welcome to RemoteHive API - Powered by MongoDB Atlas",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics"
    }

@app.get("/health")
async def health_check():
    """Simple health check endpoint for Kubernetes probes"""
    try:
        # Simple health check without monitoring system dependency
        from datetime import datetime
        return {
            "status": "healthy",
            "service": "RemoteHive API",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0"
        }
    except Exception as e:
        app_logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy", 
            "service": "RemoteHive API", 
            "error": str(e)
        }

@app.get("/metrics", include_in_schema=False)
async def get_metrics():
    """Get application metrics"""
    try:
        # Return simple metrics without complex objects that can't be serialized
        monitoring_data = app_monitor.get_monitoring_data()
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "health_summary": monitoring_data.get("health", {}).get("summary", {}),
            "system_metrics": monitoring_data.get("system", {})
        }
    except Exception as e:
        app_logger.error(f"Failed to get metrics: {e}")
        return {"error": "Failed to retrieve metrics"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )