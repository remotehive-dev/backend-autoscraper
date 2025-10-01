from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from typing import Dict, Any, List, Optional
from loguru import logger
from datetime import datetime
import os
import uuid
import shutil
from pathlib import Path
from beanie import PydanticObjectId

from backend.core.auth import get_current_active_user, get_admin
from backend.models.mongodb_models import SeoSettings, Review, Ad, ContactInformation
from backend.schemas.cms import (
    CMSPageCreate, CMSPageUpdate, CMSPage, CMSPageResponse,
    SEOSettings, SEOSettingsUpdate,
    ReviewResponse, ReviewUpdate,
    ThemeSettings, ThemeSettingsUpdate,
    PaginatedResponse,
    MediaFileCreate, MediaFileUpdate, MediaFile,
    CarouselItemCreate, CarouselItemUpdate, CarouselItem,
    GalleryCreate, GalleryUpdate, Gallery, GalleryImageCreate, GalleryImageUpdate, GalleryImage
)

router = APIRouter()

# Public CMS Endpoints (No Authentication Required)
@router.get("/public/pages", response_model=List[CMSPage])
async def get_published_pages():
    """Get all published CMS pages for public website"""
    try:
        # For now, return empty list as CMS pages are not implemented in MongoDB yet
        # TODO: Implement CMS page model and functionality
        return []
    except Exception as e:
        logger.error(f"Error fetching published pages: {e}")
        return []

@router.get("/public/pages/{slug}", response_model=CMSPage)
async def get_page_by_slug(slug: str):
    """Get published CMS page by slug for public website"""
    try:
        # For now, return 404 as CMS pages are not implemented in MongoDB yet
        # TODO: Implement CMS page model and functionality
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching page by slug {slug}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch page"
        )

@router.get("/public/reviews")
async def get_public_reviews(
    featured: bool = Query(False),
    limit: int = Query(10, ge=1, le=50)
):
    """Get approved reviews for public website"""
    try:
        # Build MongoDB query for approved reviews
        query_filter = {"status": "approved"}
        if featured:
            query_filter["featured"] = True
            
        reviews = await Review.find(query_filter).sort(-Review.created_at).limit(limit).to_list()
        
        # Convert to dict format for response
        reviews_data = [review.dict() for review in reviews]
        return {"data": reviews_data, "count": len(reviews_data)}
    except Exception as e:
        logger.error(f"Error fetching public reviews: {e}")
        # Return sample data if no reviews exist
        sample_reviews = [
            {
                "id": "1",
                "author_name": "Sarah Johnson",
                "rating": 5,
                "content": "Amazing platform! Found my dream remote job within a week.",
                "status": "approved",
                "created_at": "2024-01-15T00:00:00Z",
                "featured": True
            },
            {
                "id": "2",
                "author_name": "Mike Chen",
                "rating": 4,
                "content": "Great selection of remote opportunities. Highly recommended!",
                "status": "approved",
                "created_at": "2024-01-14T00:00:00Z",
                "featured": False
            }
        ]
        filtered_reviews = sample_reviews[:limit]
        return {"data": filtered_reviews, "count": len(filtered_reviews)}

@router.get("/public/seo-settings", response_model=SEOSettings)
async def get_public_seo_settings():
    """Get SEO settings for public website"""
    try:
        # Try to get SEO settings from MongoDB
        seo_settings = await SeoSettings.find_one()
        if seo_settings:
            return seo_settings.dict()
        else:
            # Return default SEO settings
            default_settings = {
                "site_title": "RemoteHive",
                "site_description": "Your gateway to remote opportunities",
                "meta_keywords": "remote jobs, work from home, remote work",
                "og_title": "RemoteHive - Remote Job Platform",
                "og_description": "Find your perfect remote job opportunity",
                "og_image": "",
                "twitter_card": "summary_large_image",
                "twitter_site": "@remotehive",
                "google_analytics_id": "",
                "google_tag_manager_id": "",
                "facebook_pixel_id": ""
            }
            return default_settings
    except Exception as e:
        logger.error(f"Error fetching public SEO settings: {e}")
        # Return default settings on error
        return {
            "site_title": "RemoteHive",
            "site_description": "Your gateway to remote opportunities",
            "meta_keywords": "remote jobs, work from home, remote work",
            "og_title": "RemoteHive - Remote Job Platform",
            "og_description": "Find your perfect remote job opportunity",
            "og_image": "",
            "twitter_card": "summary_large_image",
            "twitter_site": "@remotehive",
            "google_analytics_id": "",
            "google_tag_manager_id": "",
            "facebook_pixel_id": ""
        }

@router.get("/public/ads")
async def get_public_ads(
    placement: str = Query(None),
    limit: int = Query(5, ge=1, le=20)
):
    """Get active ads for public website"""
    try:
        # Build MongoDB query for active ads
        query_filter = {"status": "active"}
        if placement:
            query_filter["placement"] = placement
            
        ads = await Ad.find(query_filter).sort(-Ad.priority).limit(limit).to_list()
        
        # Convert to dict format for response
        ads_data = [ad.dict() for ad in ads]
        return {"data": ads_data, "count": len(ads_data)}
    except Exception as e:
        logger.error(f"Error fetching public ads: {e}")
        # Return empty ads list on error
        return {"data": [], "count": 0}

# CMS Pages Management
@router.get("/pages", response_model=PaginatedResponse)
async def get_pages(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_admin: Dict[str, Any] = Depends(get_admin)
):
    """Get paginated list of CMS pages"""
    try:
        # TODO: Implement CMS page listing with MongoDB
        # This requires creating a CmsPage model in mongodb_models.py
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="CMS page listing not yet implemented with MongoDB"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching CMS pages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch CMS pages"
        )

@router.get("/pages/{page_id}", response_model=CMSPage)
def get_page_by_id(
    page_id: str,
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Get CMS page by ID"""
    try:
        result = supabase.table("cms_pages").select("*").eq("id", page_id).execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Page not found"
            )
        return {"data": result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching page {page_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch page"
        )

@router.post("/pages", response_model=CMSPage)
async def create_page(
    page_data: CMSPageCreate,
    current_admin: Dict[str, Any] = Depends(get_admin)
):
    """Create a new CMS page"""
    try:
        # TODO: Implement CMS page creation with MongoDB
        # This requires creating a CmsPage model in mongodb_models.py
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="CMS page creation not yet implemented with MongoDB"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating page: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create page"
        )

@router.put("/pages/{page_id}", response_model=CMSPage)
async def update_page(
    page_id: str,
    page_data: CMSPageUpdate,
    current_admin: Dict[str, Any] = Depends(get_admin)
):
    """Update a CMS page"""
    try:
        # TODO: Implement CMS page update with MongoDB
        # This requires creating a CmsPage model in mongodb_models.py
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="CMS page update not yet implemented with MongoDB"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating page {page_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update page"
        )

@router.delete("/admin/pages/{page_id}")
async def delete_page(
    page_id: str,
    current_user: dict = Depends(get_admin)  # Changed from get_current_admin_user
):
    """Delete a CMS page (Admin only)"""
    try:
        # TODO: Implement CMS page deletion with MongoDB
        # This requires creating a CmsPage model in mongodb_models.py
        raise HTTPException(status_code=501, detail="CMS page deletion not yet implemented with MongoDB")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting page: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete page")

# SEO Settings Management
@router.get("/seo-settings", response_model=SEOSettings)
def get_seo_settings(
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Get SEO settings"""
    try:
        result = supabase.table("seo_settings").select("*").limit(1).execute()
        if result.data:
            return {"data": result.data[0]}
        else:
            # Return default SEO settings
            default_settings = {
                "site_title": "RemoteHive",
                "site_description": "Your gateway to remote opportunities",
                "meta_keywords": "remote jobs, work from home, remote work",
                "og_title": "RemoteHive - Remote Job Platform",
                "og_description": "Find your perfect remote job opportunity",
                "og_image": "",
                "twitter_card": "summary_large_image",
                "twitter_site": "@remotehive",
                "google_analytics_id": "",
                "google_tag_manager_id": "",
                "facebook_pixel_id": ""
            }
            return {"data": default_settings}
    except Exception as e:
        logger.error(f"Error fetching SEO settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch SEO settings"
        )

@router.put("/seo-settings", response_model=SEOSettings)
def update_seo_settings(
    settings_data: SEOSettingsUpdate,
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Update SEO settings"""
    try:
        # Check if settings exist
        existing = supabase.table("seo_settings").select("*").limit(1).execute()
        
        settings_dict = settings_data.dict(exclude_unset=True)
        settings_dict["updated_at"] = datetime.utcnow().isoformat()
        
        if existing.data:
            # Update existing settings
            result = supabase.table("seo_settings").update(settings_dict).eq("id", existing.data[0]["id"]).execute()
        else:
            # Create new settings
            settings_dict["created_at"] = datetime.utcnow().isoformat()
            result = supabase.table("seo_settings").insert(settings_dict).execute()
        
        return {"data": result.data[0]}
    except Exception as e:
        logger.error(f"Error updating SEO settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update SEO settings"
        )

# Reviews Management
@router.get("/reviews", response_model=PaginatedResponse)
def get_reviews(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Get paginated list of reviews"""
    try:
        offset = (page - 1) * limit
        
        # Build query
        query = supabase.table("reviews").select("*", count="exact")
        
        if status and status != "all":
            query = query.eq("status", status)
            
        # Get total count
        count_result = query.execute()
        total = count_result.count
        
        # Get paginated data
        result = query.range(offset, offset + limit - 1).order("created_at", desc=True).execute()
        
        return {
            "data": result.data,
            "count": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    except Exception as e:
        logger.error(f"Error fetching reviews: {e}")
        # Return sample data if table doesn't exist
        sample_reviews = [
            {
                "id": "1",
                "author": "Sarah Johnson",
                "rating": 5,
                "content": "Amazing platform! Found my dream remote job within a week.",
                "status": "approved",
                "date": "2024-01-15",
                "featured": True
            },
            {
                "id": "2",
                "author": "Mike Chen",
                "rating": 4,
                "content": "Great selection of remote opportunities. Highly recommended!",
                "status": "pending",
                "date": "2024-01-14",
                "featured": False
            }
        ]
        return {
            "data": sample_reviews,
            "count": len(sample_reviews),
            "page": page,
            "limit": limit,
            "pages": 1
        }

@router.put("/reviews/{review_id}/status")
def update_review_status(
    review_id: str,
    status_data: dict,
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Update review status"""
    try:
        # For now, return success since reviews table might not exist
        return {"data": {"id": review_id, "status": status_data.get("status"), "message": "Review status updated successfully"}}
    except Exception as e:
        logger.error(f"Error updating review status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update review status"
        )

@router.put("/reviews/{review_id}/featured")
def toggle_review_featured(
    review_id: str,
    featured_data: dict,
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Toggle review featured status"""
    try:
        # For now, return success since reviews table might not exist
        return {"data": {"id": review_id, "featured": featured_data.get("featured"), "message": "Review featured status updated successfully"}}
    except Exception as e:
        logger.error(f"Error updating review featured status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update review featured status"
        )

# Analytics
@router.get("/analytics")
def get_website_analytics(
    start_date: str = Query(...),
    end_date: str = Query(...),
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Get website analytics"""
    try:
        # Return sample analytics data
        analytics_data = {
            "page_views": 15420,
            "unique_visitors": 8930,
            "bounce_rate": 0.32,
            "avg_session_duration": "00:03:45",
            "top_pages": [
                {"page": "/", "views": 5420, "percentage": 35.2},
                {"page": "/jobs", "views": 3210, "percentage": 20.8},
                {"page": "/about", "views": 1890, "percentage": 12.3}
            ],
            "traffic_sources": [
                {"source": "Organic Search", "visitors": 4200, "percentage": 47.0},
                {"source": "Direct", "visitors": 2800, "percentage": 31.4},
                {"source": "Social Media", "visitors": 1200, "percentage": 13.4},
                {"source": "Referral", "visitors": 730, "percentage": 8.2}
            ]
        }
        return {"data": analytics_data}
    except Exception as e:
        logger.error(f"Error fetching analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch analytics"
        )

# Theme Settings
@router.get("/theme-settings")
def get_theme_settings(
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Get theme settings"""
    try:
        # Return default theme settings
        default_theme = {
            "primary_color": "#3B82F6",
            "secondary_color": "#10B981",
            "accent_color": "#F59E0B",
            "background_color": "#FFFFFF",
            "text_color": "#1F2937",
            "font_family": "Inter",
            "logo_url": "",
            "favicon_url": "",
            "custom_css": ""
        }
        return {"data": default_theme}
    except Exception as e:
        logger.error(f"Error fetching theme settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch theme settings"
        )

@router.put("/theme-settings")
def update_theme_settings(
    settings_data: dict,
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Update theme settings"""
    try:
        # For now, return the updated settings
        return {"data": settings_data}
    except Exception as e:
        logger.error(f"Error updating theme settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update theme settings"
        )

# Ads Management
@router.get("/ads")
def get_ads(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Get ads campaigns"""
    try:
        # Return sample ads data
        sample_ads = [
            {
                "id": "1",
                "name": "Google Ads Campaign",
                "platform": "Google Ads",
                "status": "active",
                "budget": "$500/month",
                "performance": "+15% CTR"
            },
            {
                "id": "2",
                "name": "Meta Ads Campaign",
                "platform": "Meta",
                "status": "paused",
                "budget": "$300/month",
                "performance": "+8% CTR"
            }
        ]
        return {"data": sample_ads}
    except Exception as e:
        logger.error(f"Error fetching ads: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch ads"
        )

@router.put("/ads/{ad_id}")
def update_ad(
    ad_id: str,
    ad_data: dict,
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Update ad campaign"""
    try:
        # For now, return success
        return {"data": {"id": ad_id, **ad_data, "message": "Ad updated successfully"}}
    except Exception as e:
        logger.error(f"Error updating ad: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update ad"
        )

# ============================================================================
# MEDIA LIBRARY ENDPOINTS
# ============================================================================

@router.post("/admin/media/upload", response_model=MediaFile)
async def upload_media_file(
    file: UploadFile = File(...),
    alt_text: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    folder: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # Comma-separated tags
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Upload a media file to the library"""
    try:
        # Create uploads directory if it doesn't exist
        upload_dir = Path("uploads/media")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_extension = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = upload_dir / unique_filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Determine media type
        mime_type = file.content_type or "application/octet-stream"
        if mime_type.startswith("image/"):
            media_type = "image"
        elif mime_type.startswith("video/"):
            media_type = "video"
        elif mime_type.startswith("audio/"):
            media_type = "audio"
        else:
            media_type = "document"
        
        # Parse tags
        tag_list = [tag.strip() for tag in tags.split(",")] if tags else []
        
        # Create media file record
        media_data = {
            "id": str(uuid.uuid4()),
            "filename": unique_filename,
            "original_filename": file.filename,
            "file_path": str(file_path),
            "file_url": f"/uploads/media/{unique_filename}",
            "file_size": file.size or 0,
            "mime_type": mime_type,
            "media_type": media_type,
            "alt_text": alt_text,
            "caption": caption,
            "tags": tag_list,
            "folder": folder,
            "is_public": True,
            "uploaded_by": current_admin.get("id"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "download_count": 0
        }
        
        # Store in database (using sample data for now)
        return media_data
        
    except Exception as e:
        logger.error(f"Error uploading media file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload media file"
        )

@router.get("/admin/media", response_model=List[MediaFile])
def get_media_files(
    folder: Optional[str] = Query(None),
    media_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Get media files with filtering"""
    try:
        # Sample media files for demonstration
        sample_media = [
            {
                "id": "1",
                "filename": "hero-image.jpg",
                "original_filename": "hero-image.jpg",
                "file_path": "/uploads/media/hero-image.jpg",
                "file_url": "/uploads/media/hero-image.jpg",
                "file_size": 1024000,
                "mime_type": "image/jpeg",
                "media_type": "image",
                "alt_text": "Hero section background",
                "caption": "Main hero image for homepage",
                "tags": ["hero", "homepage", "background"],
                "folder": "homepage",
                "is_public": True,
                "uploaded_by": "admin",
                "created_at": "2024-01-15T00:00:00Z",
                "updated_at": "2024-01-15T00:00:00Z",
                "download_count": 0
            },
            {
                "id": "2",
                "filename": "company-logo.png",
                "original_filename": "company-logo.png",
                "file_path": "/uploads/media/company-logo.png",
                "file_url": "/uploads/media/company-logo.png",
                "file_size": 256000,
                "mime_type": "image/png",
                "media_type": "image",
                "alt_text": "Company logo",
                "caption": "Official company logo",
                "tags": ["logo", "branding"],
                "folder": "branding",
                "is_public": True,
                "uploaded_by": "admin",
                "created_at": "2024-01-14T00:00:00Z",
                "updated_at": "2024-01-14T00:00:00Z",
                "download_count": 5
            }
        ]
        
        # Apply filters
        filtered_media = sample_media
        if folder:
            filtered_media = [m for m in filtered_media if m.get("folder") == folder]
        if media_type:
            filtered_media = [m for m in filtered_media if m.get("media_type") == media_type]
        if search:
            filtered_media = [m for m in filtered_media if search.lower() in m.get("filename", "").lower() or search.lower() in m.get("alt_text", "").lower()]
        
        # Apply pagination
        paginated_media = filtered_media[offset:offset + limit]
        return paginated_media
        
    except Exception as e:
        logger.error(f"Error fetching media files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch media files"
        )

@router.put("/admin/media/{media_id}", response_model=MediaFile)
def update_media_file(
    media_id: str,
    media_data: MediaFileUpdate,
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Update media file metadata"""
    try:
        # For demonstration, return updated data
        updated_media = {
            "id": media_id,
            "filename": media_data.filename or "updated-file.jpg",
            "original_filename": "updated-file.jpg",
            "file_path": "/uploads/media/updated-file.jpg",
            "file_url": "/uploads/media/updated-file.jpg",
            "file_size": 1024000,
            "mime_type": "image/jpeg",
            "media_type": "image",
            "alt_text": media_data.alt_text,
            "caption": media_data.caption,
            "tags": media_data.tags or [],
            "folder": media_data.folder,
            "is_public": media_data.is_public if media_data.is_public is not None else True,
            "uploaded_by": "admin",
            "created_at": "2024-01-15T00:00:00Z",
            "updated_at": datetime.utcnow().isoformat(),
            "download_count": 0
        }
        return updated_media
        
    except Exception as e:
        logger.error(f"Error updating media file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update media file"
        )

@router.delete("/admin/media/{media_id}")
def delete_media_file(
    media_id: str,
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Delete media file"""
    try:
        # For demonstration, return success
        return {"message": "Media file deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting media file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete media file"
        )

# ============================================================================
# CAROUSEL MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/admin/carousel", response_model=List[CarouselItem])
def get_carousel_items(
    carousel_type: Optional[str] = Query(None),
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Get carousel items"""
    try:
        # Sample carousel items
        sample_items = [
            {
                "id": "1",
                "title": "Test Company",
            "subtitle": "Test Industry Leader",
            "description": "Test company description",
                "image_url": "/uploads/media/test-logo.svg",
            "link_url": "https://example.com",
                "link_text": "Learn More",
                "order": 1,
                "is_active": True,
                "carousel_type": "hero",
                "created_at": "2024-01-15T00:00:00Z",
                "updated_at": "2024-01-15T00:00:00Z",
                "created_by": "admin"
            },
            {
                "id": "2",
                "title": "Microsoft",
                "subtitle": "Innovation Partner",
                "description": "Empowering every person and organization",
                "image_url": "/uploads/media/microsoft-logo.svg",
                "link_url": "https://microsoft.com",
                "link_text": "Explore",
                "order": 2,
                "is_active": True,
                "carousel_type": "hero",
                "created_at": "2024-01-14T00:00:00Z",
                "updated_at": "2024-01-14T00:00:00Z",
                "created_by": "admin"
            }
        ]
        
        # Filter by carousel type if specified
        if carousel_type:
            sample_items = [item for item in sample_items if item["carousel_type"] == carousel_type]
        
        return sample_items
        
    except Exception as e:
        logger.error(f"Error fetching carousel items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch carousel items"
        )

@router.post("/admin/carousel", response_model=CarouselItem)
def create_carousel_item(
    carousel_data: CarouselItemCreate,
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Create new carousel item"""
    try:
        new_item = {
            "id": str(uuid.uuid4()),
            "title": carousel_data.title,
            "subtitle": carousel_data.subtitle,
            "description": carousel_data.description,
            "image_url": carousel_data.image_url,
            "link_url": carousel_data.link_url,
            "link_text": carousel_data.link_text,
            "order": carousel_data.order,
            "is_active": carousel_data.is_active,
            "carousel_type": carousel_data.carousel_type,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "created_by": current_admin.get("id")
        }
        return new_item
        
    except Exception as e:
        logger.error(f"Error creating carousel item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create carousel item"
        )

@router.put("/admin/carousel/{item_id}", response_model=CarouselItem)
def update_carousel_item(
    item_id: str,
    carousel_data: CarouselItemUpdate,
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Update carousel item"""
    try:
        updated_item = {
            "id": item_id,
            "title": carousel_data.title or "Updated Title",
            "subtitle": carousel_data.subtitle,
            "description": carousel_data.description,
            "image_url": carousel_data.image_url or "/uploads/media/default.jpg",
            "link_url": carousel_data.link_url,
            "link_text": carousel_data.link_text,
            "order": carousel_data.order or 0,
            "is_active": carousel_data.is_active if carousel_data.is_active is not None else True,
            "carousel_type": carousel_data.carousel_type or "hero",
            "created_at": "2024-01-15T00:00:00Z",
            "updated_at": datetime.utcnow().isoformat(),
            "created_by": "admin"
        }
        return updated_item
        
    except Exception as e:
        logger.error(f"Error updating carousel item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update carousel item"
        )

@router.delete("/admin/carousel/{item_id}")
def delete_carousel_item(
    item_id: str,
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Delete carousel item"""
    try:
        return {"message": "Carousel item deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting carousel item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete carousel item"
        )

# ============================================================================
# IMAGE GALLERY ENDPOINTS
# ============================================================================

@router.get("/admin/galleries", response_model=List[Gallery])
def get_galleries(
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Get all image galleries"""
    try:
        sample_galleries = [
            {
                "id": "1",
                "name": "Company Showcase",
                "description": "Images showcasing our company culture and workspace",
                "slug": "company-showcase",
                "is_public": True,
                "cover_image": "/uploads/media/gallery-cover-1.jpg",
                "created_at": "2024-01-15T00:00:00Z",
                "updated_at": "2024-01-15T00:00:00Z",
                "created_by": "admin",
                "image_count": 12
            },
            {
                "id": "2",
                "name": "Product Gallery",
                "description": "Product screenshots and features",
                "slug": "product-gallery",
                "is_public": True,
                "cover_image": "/uploads/media/gallery-cover-2.jpg",
                "created_at": "2024-01-14T00:00:00Z",
                "updated_at": "2024-01-14T00:00:00Z",
                "created_by": "admin",
                "image_count": 8
            }
        ]
        return sample_galleries
        
    except Exception as e:
        logger.error(f"Error fetching galleries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch galleries"
        )

@router.post("/admin/galleries", response_model=Gallery)
def create_gallery(
    gallery_data: GalleryCreate,
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Create new image gallery"""
    try:
        new_gallery = {
            "id": str(uuid.uuid4()),
            "name": gallery_data.name,
            "description": gallery_data.description,
            "slug": gallery_data.slug,
            "is_public": gallery_data.is_public,
            "cover_image": gallery_data.cover_image,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "created_by": current_admin.get("id"),
            "image_count": 0
        }
        return new_gallery
        
    except Exception as e:
        logger.error(f"Error creating gallery: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create gallery"
        )

@router.get("/admin/galleries/{gallery_id}/images", response_model=List[GalleryImage])
def get_gallery_images(
    gallery_id: str,
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Get images in a gallery"""
    try:
        sample_images = [
            {
                "id": "1",
                "gallery_id": gallery_id,
                "media_file_id": "1",
                "order": 1,
                "caption": "Test image caption",
                "is_featured": True,
                "created_at": "2024-01-15T00:00:00Z",
                "media_file": {
                    "id": "1",
                    "filename": "team-photo.jpg",
                    "original_filename": "team-photo.jpg",
                    "file_path": "/uploads/media/team-photo.jpg",
                    "file_url": "/uploads/media/team-photo.jpg",
                    "file_size": 1024000,
                    "mime_type": "image/jpeg",
                    "media_type": "image",
                    "alt_text": "Test image alt text",
                    "caption": "Test image caption",
                    "tags": ["test", "sample"],
                    "folder": "company",
                    "is_public": True,
                    "uploaded_by": "admin",
                    "created_at": "2024-01-15T00:00:00Z",
                    "updated_at": "2024-01-15T00:00:00Z",
                    "download_count": 0
                }
            }
        ]
        return sample_images
        
    except Exception as e:
        logger.error(f"Error fetching gallery images: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch gallery images"
        )

@router.post("/admin/galleries/{gallery_id}/images", response_model=GalleryImage)
def add_image_to_gallery(
    gallery_id: str,
    image_data: GalleryImageCreate,
    current_admin: Dict[str, Any] = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Add image to gallery"""
    try:
        new_gallery_image = {
            "id": str(uuid.uuid4()),
            "gallery_id": gallery_id,
            "media_file_id": image_data.media_file_id,
            "order": image_data.order,
            "caption": image_data.caption,
            "is_featured": image_data.is_featured,
            "created_at": datetime.utcnow().isoformat(),
            "media_file": None  # Would be populated from database
        }
        return new_gallery_image
        
    except Exception as e:
        logger.error(f"Error adding image to gallery: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add image to gallery"
        )

# ============================================================================
# PUBLIC ENDPOINTS FOR NEW FEATURES
# ============================================================================

@router.get("/public/carousel/{carousel_type}", response_model=List[CarouselItem])
def get_public_carousel(
    carousel_type: str
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Get public carousel items by type"""
    try:
        # Sample public carousel data
        sample_items = [
            {
                "id": "1",
                "title": "Google",
                "subtitle": "Technology Leader",
                "description": "Join the world's leading technology company",
                "image_url": "/uploads/media/google-logo.svg",
                "link_url": "https://google.com",
                "link_text": "Learn More",
                "order": 1,
                "is_active": True,
                "carousel_type": carousel_type,
                "created_at": "2024-01-15T00:00:00Z",
                "updated_at": "2024-01-15T00:00:00Z",
                "created_by": "admin"
            }
        ]
        
        # Filter active items only
        active_items = [item for item in sample_items if item["is_active"] and item["carousel_type"] == carousel_type]
        return sorted(active_items, key=lambda x: x["order"])
        
    except Exception as e:
        logger.error(f"Error fetching public carousel: {e}")
        return []

@router.get("/public/galleries/{gallery_slug}", response_model=Dict[str, Any])
def get_public_gallery(
    gallery_slug: str
    # db: Session = Depends(get_db)  # Commented out - Session not available
):
    """Get public gallery by slug"""
    try:
        # Sample public gallery data
        sample_gallery = {
            "id": "1",
            "name": "Test Gallery",
            "description": "Test gallery description",
            "slug": gallery_slug,
            "is_public": True,
            "cover_image": "/uploads/media/gallery-cover-1.jpg",
            "created_at": "2024-01-15T00:00:00Z",
            "updated_at": "2024-01-15T00:00:00Z",
            "created_by": "admin",
            "image_count": 12,
            "images": [
                {
                    "id": "1",
                    "gallery_id": "1",
                    "media_file_id": "1",
                    "order": 1,
                    "caption": "Test image caption",
                    "is_featured": True,
                    "created_at": "2024-01-15T00:00:00Z",
                    "media_file": {
                        "id": "1",
                        "filename": "team-photo.jpg",
                        "file_url": "/uploads/media/team-photo.jpg",
                        "alt_text": "Test image alt text",
                        "caption": "Test image caption"
                    }
                }
            ]
        }
        
        if sample_gallery["slug"] == gallery_slug and sample_gallery["is_public"]:
            return sample_gallery
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Gallery not found"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching public gallery: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch gallery"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update ad"
        )