from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response, StreamingResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging
import uuid
import io
from datetime import datetime

from backend.core.deps import get_database, get_current_user
from backend.models.mongodb_models import User
from backend.services.website_management_service import WebsiteManagementService
from backend.services.website_template_service import WebsiteTemplateService
from backend.schemas.website_management import (
    WebsiteStatus, WebsiteConfig, WebsiteUploadResponse, WebsiteUploadStatus,
    WebsiteValidationResult, ManagedWebsiteResponse, WebsiteCreateRequest, WebsiteUpdateRequest
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", response_model=Dict[str, List[Any]])
async def get_websites(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Get all websites for the frontend"""
    website_service = WebsiteManagementService(db)
    
    try:
        websites = await website_service.list_websites(
            user_id=current_user.id,
            limit=50,
            offset=0
        )
        return {"websites": websites}
    except Exception as e:
        logger.error(f"Error getting websites: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Additional Models for bulk operations

class BulkWebsiteConfig(BaseModel):
    websites: List[WebsiteConfig]
    default_rate_limit: int = Field(default=5, description="Default rate limit for all websites")
    default_max_pages: int = Field(default=100, description="Default max pages for all websites")
    enable_validation: bool = Field(default=True, description="Enable URL validation")
    auto_categorize: bool = Field(default=False, description="Auto-categorize websites using ML")

# API Endpoints
@router.get("/template", response_class=StreamingResponse)
async def download_website_template():
    """Download CSV template for bulk website upload."""
    
    template_service = WebsiteTemplateService()
    template_content = template_service.generate_template()
    filename = template_service.get_template_filename()
    
    return StreamingResponse(
        io.BytesIO(template_content.encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/template/info")
async def get_template_info():
    """Get information about the website CSV template."""
    
    template_service = WebsiteTemplateService()
    return template_service.get_template_info()

@router.post("/upload", response_model=WebsiteUploadResponse)
async def upload_websites(
    file: UploadFile = File(...),
    enable_validation: bool = Form(True),
    auto_categorize: bool = Form(False),
    default_rate_limit: int = Form(5),
    default_max_pages: int = Form(100),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """
    Upload websites in bulk via CSV file.
    
    Args:
        file: CSV file containing website configurations
        enable_validation: Enable URL validation
        auto_categorize: Auto-categorize websites using ML
        default_rate_limit: Default rate limit for websites
        default_max_pages: Default max pages for websites
    
    Returns:
        Upload response with status and progress information
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    website_service = WebsiteManagementService(db)
    
    try:
        # Read file content
        content = await file.read()
        
        # Process upload
        upload_response = await website_service.process_bulk_upload(
            csv_content=content.decode('utf-8'),
            user_id=current_user.id,
            enable_validation=enable_validation,
            auto_categorize=auto_categorize,
            default_rate_limit=default_rate_limit,
            default_max_pages=default_max_pages
        )
        
        return upload_response
        
    except Exception as e:
        logger.error(f"Error processing website upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/status/{upload_id}", response_model=WebsiteUploadStatus)
async def get_upload_status(
    upload_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """
    Get the status of a website upload.
    
    Args:
        upload_id: Upload ID to check status for
    
    Returns:
        Upload status with progress information
    """
    website_service = WebsiteManagementService(db)
    
    try:
        status = await website_service.get_upload_status(upload_id, current_user.id)
        if not status:
            raise HTTPException(status_code=404, detail="Upload not found")
        return status
    except Exception as e:
        logger.error(f"Error getting upload status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get upload status")

@router.get("/history")
async def get_upload_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """
    Get upload history for the current user.
    
    Args:
        limit: Maximum number of records to return
        offset: Number of records to skip
    
    Returns:
        List of upload history records
    """
    website_service = WebsiteManagementService(db)
    
    try:
        history = await website_service.get_upload_history(
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        return history
    except Exception as e:
        logger.error(f"Error getting upload history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get upload history")

@router.delete("/cancel/{upload_id}")
async def cancel_upload(
    upload_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """
    Cancel an ongoing website upload.
    
    Args:
        upload_id: Upload ID to cancel
    
    Returns:
        Cancellation confirmation
    """
    website_service = WebsiteManagementService(db)
    
    try:
        result = await website_service.cancel_upload(upload_id, current_user.id)
        if not result:
            raise HTTPException(status_code=404, detail="Upload not found or cannot be cancelled")
        return {"message": "Upload cancelled successfully"}
    except Exception as e:
        logger.error(f"Error cancelling upload: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cancel upload")

@router.post("/validate", response_model=WebsiteValidationResult)
async def validate_websites(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Validate website CSV without uploading.
    
    Args:
        file: CSV file to validate
    
    Returns:
        Validation results with errors and warnings
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    website_service = WebsiteManagementService(None)
    
    try:
        content = await file.read()
        validation_result = await website_service.validate_website_csv(
            csv_content=content.decode('utf-8')
        )
        return validation_result
    except Exception as e:
        logger.error(f"Error validating websites: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

@router.get("/stats")
async def get_website_stats(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """
    Get website management statistics.
    
    Returns:
        Statistics about managed websites
    """
    website_service = WebsiteManagementService(db)
    
    try:
        stats = await website_service.get_website_stats(current_user.id)
        return stats
    except Exception as e:
        logger.error(f"Error getting website stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get website statistics")

@router.get("/list")
async def list_websites(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_database),  # Using MongoDB instead
    current_user: User = Depends(get_current_user)
):
    """
    List managed websites with filtering options.
    
    Args:
        category: Filter by website category
        status: Filter by website status
        limit: Maximum number of records to return
        offset: Number of records to skip
    
    Returns:
        List of managed websites
    """
    website_service = WebsiteManagementService(db)
    
    try:
        websites = await website_service.list_websites(
            user_id=current_user.id,
            category=category,
            status=status,
            limit=limit,
            offset=offset
        )
        return websites
    except Exception as e:
        logger.error(f"Error listing websites: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list websites")

@router.put("/update/{website_id}")
async def update_website(
    website_id: int,
    website_config: WebsiteConfig,
    db: AsyncIOMotorDatabase = Depends(get_database),  # Using MongoDB instead
    current_user: User = Depends(get_current_user)
):
    """
    Update a managed website configuration.
    
    Args:
        website_id: Website ID to update
        website_config: Updated website configuration
    
    Returns:
        Updated website information
    """
    website_service = WebsiteManagementService(db)
    
    try:
        updated_website = await website_service.update_website(
            website_id=website_id,
            user_id=current_user.id,
            website_config=website_config
        )
        if not updated_website:
            raise HTTPException(status_code=404, detail="Website not found")
        return updated_website
    except Exception as e:
        logger.error(f"Error updating website: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update website")

@router.delete("/delete/{website_id}")
async def delete_website(
    website_id: int,
    db: AsyncIOMotorDatabase = Depends(get_database),  # Using MongoDB instead
    current_user: User = Depends(get_current_user)
):
    """
    Delete a managed website.
    
    Args:
        website_id: Website ID to delete
    
    Returns:
        Deletion confirmation
    """
    website_service = WebsiteManagementService(db)
    
    try:
        result = await website_service.delete_website(website_id, current_user.id)
        if not result:
            raise HTTPException(status_code=404, detail="Website not found")
        return {"message": "Website deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting website: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete website")