from fastapi import APIRouter
from backend.api.v1.endpoints import (
    auth_endpoints,
    users,
    jobs,
    employers,
    job_seekers,
    applications,
    admin,
    notifications,
    health,
    companies,
    cms,
    contact,
    contact_info,
    location,
    payments,
    support_endpoints,
    email_management,
    email_users,
    csv_upload,
    website_management,
    ml_intelligence,
    memory_loader,
    websocket,
    slack_admin,
    scraper_configs,
    password_reset,
    oauth,
    leads,
    job_workflow,
    advanced_job_workflow,
    clerk_auth_endpoints
)
from backend.autoscraper.endpoints import router as autoscraper_router

api_router = APIRouter()

# Essential endpoints only - gradually adding back to identify CallableSchema issue
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth_endpoints.router, prefix="/auth", tags=["authentication"])
api_router.include_router(oauth.router, prefix="/auth", tags=["oauth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(employers.router, prefix="/employers", tags=["employers"])
api_router.include_router(job_seekers.router, prefix="/job-seekers", tags=["job-seekers"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(csv_upload.router, prefix="/csv", tags=["csv-upload"])
api_router.include_router(autoscraper_router, prefix="/autoscraper", tags=["autoscraper"])

# Test endpoint for docs functionality
@api_router.get("/test")
async def test_endpoint():
    """Test endpoint to verify API is working"""
    return {"message": "API is working", "status": "ok"}
