from fastapi import APIRouter, Depends, HTTPException, status, Query
# TODO: MongoDB Migration - Remove SQLAlchemy dependency
# from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database.database import get_db_session
from backend.services.scraper_config_service import ScraperConfigService
from backend.schemas.scraper_config import (
    ScraperConfigCreate,
    ScraperConfigUpdate,
    ScraperConfigResponse,
    ScraperConfigListResponse,
    ScraperConfigStats,
    BulkScraperConfigCreate,
    BulkScraperConfigResponse
)
from backend.core.auth import get_current_user
# TODO: MongoDB Migration - Update User import to use MongoDB models
# from backend.database.models import User
from backend.models.mongodb_models import User

router = APIRouter()

# Schemas are now imported from backend.schemas.scraper_config

@router.get("/configs", response_model=ScraperConfigListResponse)
async def get_scraper_configs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db = Depends(get_db_session),  # TODO: MongoDB Migration - Remove Session type
    current_user: User = Depends(get_current_user)
):
    """
    Get all scraper configurations for the current user or all configs for admin users
    """
    service = ScraperConfigService(db)
    user_id = None if current_user.role.value in ['admin', 'super_admin'] else current_user.id
    configs = service.get_all_configs(skip=skip, limit=limit, user_id=user_id)
    total = len(configs)  # In a real implementation, you'd get the total count separately
    
    return ScraperConfigListResponse(
        configs=configs,
        total=total,
        skip=skip,
        limit=limit
    )

@router.post("/configs", response_model=ScraperConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_scraper_config(
    config_data: ScraperConfigCreate,
    db = Depends(get_db_session),  # TODO: MongoDB Migration - Remove Session type
    current_user: User = Depends(get_current_user)
):
    """
    Create a new scraper configuration
    """
    service = ScraperConfigService(db)
    try:
        db_config = service.create_config(config_data, current_user.id)
        return db_config
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating configuration: {str(e)}"
        )

@router.put("/configs/{config_id}", response_model=ScraperConfigResponse)
async def update_scraper_config(
    config_id: int,
    config_data: ScraperConfigUpdate,
    db = Depends(get_db_session),  # TODO: MongoDB Migration - Remove Session type
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing scraper configuration
    """
    service = ScraperConfigService(db)
    
    # Check if user has permission to update this config
    if current_user.role.value not in ['admin', 'super_admin']:
        existing_config = service.get_config_by_id(config_id)
        if not existing_config or existing_config.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scraper configuration not found"
            )
    
    db_config = service.update_config(config_id, config_data)
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraper configuration not found"
        )
    return db_config

@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scraper_config(
    config_id: int,
    db = Depends(get_db_session),  # TODO: MongoDB Migration - Remove Session type
    current_user: User = Depends(get_current_user)
):
    """
    Delete a scraper configuration
    """
    service = ScraperConfigService(db)
    
    # Check if user has permission to delete this config
    if current_user.role.value not in ['admin', 'super_admin']:
        existing_config = service.get_config_by_id(config_id)
        if not existing_config or existing_config.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scraper configuration not found"
            )
    
    success = service.delete_config(config_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraper configuration not found"
        )
    return

@router.get("/configs/{config_id}", response_model=ScraperConfigResponse)
async def get_scraper_config(
    config_id: int,
    db = Depends(get_db_session),  # TODO: MongoDB Migration - Remove Session type
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific scraper configuration by ID
    """
    service = ScraperConfigService(db)
    config = service.get_config_by_id(config_id)
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraper configuration not found"
        )
    
    # Check if user has permission to view this config
    if current_user.role.value not in ['admin', 'super_admin'] and config.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraper configuration not found"
        )
    
    return config

@router.post("/configs/bulk", response_model=BulkScraperConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_bulk_configs(
    bulk_request: BulkScraperConfigCreate,
    db = Depends(get_db_session),  # TODO: MongoDB Migration - Remove Session type
    current_user: User = Depends(get_current_user)
):
    """
    Create multiple scraper configurations at once
    """
    service = ScraperConfigService(db)
    created_configs = []
    failed_configs = []
    
    for i, config in enumerate(bulk_request.configs):
        try:
            db_config = service.create_config(config, current_user.id)
            created_configs.append(db_config)
        except Exception as e:
            failed_configs.append({
                "index": i,
                "config_name": config.name,
                "error": str(e)
            })
    
    return BulkScraperConfigResponse(
        created=created_configs,
        failed=failed_configs,
        total_created=len(created_configs),
        total_failed=len(failed_configs)
    )

@router.delete("/configs/bulk", status_code=status.HTTP_200_OK)
async def delete_bulk_configs(
    config_ids: List[int],
    db = Depends(get_db_session),  # TODO: MongoDB Migration - Remove Session type
    current_user: User = Depends(get_current_user)
):
    """
    Delete multiple scraper configurations at once
    """
    service = ScraperConfigService(db)
    deleted_count = 0
    failed_deletions = []
    
    for config_id in config_ids:
        try:
            # Check permissions for each config
            if current_user.role.value not in ['admin', 'super_admin']:
                existing_config = service.get_config_by_id(config_id)
                if not existing_config or existing_config.user_id != current_user.id:
                    failed_deletions.append({"id": config_id, "error": "Configuration not found or access denied"})
                    continue
            
            success = service.delete_config(config_id)
            if success:
                deleted_count += 1
            else:
                failed_deletions.append({"id": config_id, "error": "Configuration not found"})
        except Exception as e:
            failed_deletions.append({"id": config_id, "error": str(e)})
    
    return {
        "deleted_count": deleted_count,
        "failed_deletions": failed_deletions,
        "total_requested": len(config_ids)
    }

@router.get("/configs/{config_id}/stats", response_model=ScraperConfigStats)
async def get_config_stats(
    config_id: int,
    db = Depends(get_db_session),  # TODO: MongoDB Migration - Remove Session type
    current_user: User = Depends(get_current_user)
):
    """
    Get statistics for a specific scraper configuration
    """
    service = ScraperConfigService(db)
    config = service.get_config_by_id(config_id)
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraper configuration not found"
        )
    
    # Check if user has permission to view this config
    if current_user.role.value not in ['admin', 'super_admin'] and config.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraper configuration not found"
        )
    
    stats = service.get_config_stats(config_id)
    return ScraperConfigStats(**stats)

@router.get("/configs/active", response_model=List[ScraperConfigResponse])
async def get_active_configs(
    db = Depends(get_db_session),  # TODO: MongoDB Migration - Remove Session type
    current_user: User = Depends(get_current_user)
):
    """
    Get all active scraper configurations
    """
    service = ScraperConfigService(db)
    user_id = None if current_user.role.value in ['admin', 'super_admin'] else current_user.id
    configs = service.get_active_configs(user_id=user_id)
    return configs

@router.get("/configs/scheduled", response_model=List[ScraperConfigResponse])
async def get_scheduled_configs(
    db = Depends(get_db_session),  # TODO: MongoDB Migration - Remove Session type
    current_user: User = Depends(get_current_user)
):
    """
    Get all configurations that have scheduling enabled (admin only)
    """
    if current_user.role.value not in ['admin', 'super_admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    service = ScraperConfigService(db)
    configs = service.get_scheduled_configs()
    return configs