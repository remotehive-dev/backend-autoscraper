from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
# from bson import ObjectId  # Removed to fix Pydantic schema generation
from backend.schemas.scraper_config import ScraperConfigCreate, ScraperConfigUpdate
from backend.core.enums import ScraperSource
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ScraperConfigService:
    """Service for managing scraper configurations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def get_all_configs(self, skip: int = 0, limit: int = 100, 
                       user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all scraper configurations with optional filtering"""
        filter_query = {}
        
        if user_id:
            filter_query["user_id"] = user_id
        
        cursor = self.db.scraper_configs.find(filter_query).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def get_config_by_id(self, config_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific scraper configuration by ID"""
        return await self.db.scraper_configs.find_one({"_id": config_id})
    
    async def create_config(self, config_data: ScraperConfigCreate, user_id: str) -> Dict[str, Any]:
        """Create a new scraper configuration"""
        try:
            # Verify user exists
            user = await self.db.users.find_one({"_id": user_id})
            if not user:
                raise ValueError(f"User with ID {user_id} not found")
            
            # Create new config document
            config_doc = {
                "user_id": user_id,
                "name": config_data.name,
                "base_url": config_data.base_url,
                "search_queries": config_data.search_queries,
                "max_pages": config_data.max_pages,
                "delay_between_requests": config_data.delay_between_requests,
                "is_active": config_data.is_active,
                "ml_parsing_enabled": config_data.ml_parsing_enabled,
                "auto_apply_enabled": config_data.auto_apply_enabled,
                "schedule_enabled": config_data.schedule_enabled,
                "schedule_interval": config_data.schedule_interval,
                "last_run_at": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = await self.db.scraper_configs.insert_one(config_doc)
            config_doc["_id"] = result.inserted_id
            
            logger.info(f"Created scraper config {result.inserted_id} for user {user_id}")
            return config_doc
            
        except Exception as e:
            logger.error(f"Error creating scraper config: {str(e)}")
            raise
    
    async def update_config(self, config_id: str, config_data: ScraperConfigUpdate) -> Optional[Dict[str, Any]]:
        """Update an existing scraper configuration"""
        try:
            # Check if config exists
            existing_config = await self.get_config_by_id(config_id)
            if not existing_config:
                return None
            
            # Update fields that are provided
            update_data = config_data.dict(exclude_unset=True)
            update_data["updated_at"] = datetime.utcnow()
            
            result = await self.db.scraper_configs.update_one(
                {"_id": config_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                updated_config = await self.get_config_by_id(config_id)
                logger.info(f"Updated scraper config {config_id}")
                return updated_config
            
            return existing_config
            
        except Exception as e:
            logger.error(f"Error updating scraper config {config_id}: {str(e)}")
            raise
    
    async def delete_config(self, config_id: str) -> bool:
        """Delete a scraper configuration"""
        try:
            # Check if config exists
            existing_config = await self.get_config_by_id(config_id)
            if not existing_config:
                return False
            
            result = await self.db.scraper_configs.delete_one({"_id": config_id})
            
            if result.deleted_count > 0:
                logger.info(f"Deleted scraper config {config_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting scraper config {config_id}: {str(e)}")
            raise
    
    async def get_active_configs(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all active scraper configurations"""
        filter_query = {"is_active": True}
        
        if user_id:
            filter_query["user_id"] = user_id
        
        cursor = self.db.scraper_configs.find(filter_query)
        return await cursor.to_list(length=None)
    
    async def get_scheduled_configs(self) -> List[Dict[str, Any]]:
        """Get all configurations that have scheduling enabled"""
        filter_query = {
            "is_active": True,
            "schedule_enabled": True
        }
        
        cursor = self.db.scraper_configs.find(filter_query)
        return await cursor.to_list(length=None)
    
    async def update_last_run(self, config_id: str) -> bool:
        """Update the last run timestamp for a configuration"""
        try:
            # Check if config exists
            existing_config = await self.get_config_by_id(config_id)
            if not existing_config:
                return False
            
            update_data = {
                "last_run_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = await self.db.scraper_configs.update_one(
                {"_id": config_id},
                {"$set": update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating last run for config {config_id}: {str(e)}")
            raise
    
    async def search_configs(self, query: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search configurations by name or base URL"""
        search_filter = {
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"base_url": {"$regex": query, "$options": "i"}}
            ]
        }
        
        if user_id:
            search_filter["user_id"] = user_id
        
        cursor = self.db.scraper_configs.find(search_filter)
        return await cursor.to_list(length=None)
    
    async def get_config_stats(self, config_id: str) -> Dict[str, Any]:
        """Get statistics for a specific configuration"""
        config = await self.get_config_by_id(config_id)
        if not config:
            return {}
        
        # Basic stats from the config itself
        stats = {
            "id": str(config["_id"]),
            "name": config.get("name"),
            "is_active": config.get("is_active"),
            "last_run_at": config.get("last_run_at"),
            "created_at": config.get("created_at"),
            "total_runs": 0,  # This would come from ScraperLog if needed
            "success_rate": 0.0,  # This would be calculated from ScraperLog
            "avg_jobs_per_run": 0.0  # This would be calculated from ScraperLog
        }
        
        return stats