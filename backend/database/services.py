from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional, Dict, Any
import json
import logging
import uuid
from datetime import datetime
from bson import ObjectId

from backend.database.mongodb_models import User, JobSeeker, Employer, JobPost, JobApplication, ScraperConfig, ScraperLog
from backend.core.password_utils import get_password_hash, verify_password

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def create_user(self, user_data: Dict[str, Any]) -> User:
        """Create a new user from dictionary data."""
        user = User(**user_data)
        user_dict = user.dict()
        result = await self.db.users.insert_one(user_dict)
        user_dict["_id"] = result.inserted_id
        return User(**user_dict)
    
    @staticmethod
    async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[User]:
        """Get user by email using Beanie ODM."""
        try:
            user = await User.find_one(User.email == email)
            return user
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email using Beanie ODM."""
        try:
            user = await User.find_one(User.email == email)
            return user
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None
    
    @staticmethod
    async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[User]:
        """Get user by ID using Beanie ODM."""
        try:
            # Convert string UUID to UUID object if needed
            uuid_obj = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            # Use Beanie ODM to find user by id
            user = await User.find_one(User.id == str(uuid_obj))
            return user
        except (ValueError, TypeError, Exception) as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID using Beanie ODM."""
        try:
            # Convert string UUID to UUID object if needed
            uuid_obj = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            # Use Beanie ODM to find user by id
            user = await User.find_one(User.id == str(uuid_obj))
            return user
        except (ValueError, TypeError, Exception) as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            return None
    
    async def update_last_login(self, user_id: str) -> Optional[User]:
        """Update user's last login timestamp."""
        try:
            uuid_obj = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            result = await self.db.users.update_one(
                {"id": str(uuid_obj)},
                {"$set": {"last_login": datetime.utcnow()}}
            )
            if result.modified_count > 0:
                user_data = await self.db.users.find_one({"id": str(uuid_obj)})
                return User(**user_data) if user_data else None
            return None
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    async def authenticate_user(db: AsyncIOMotorDatabase, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password."""
        user = await UserService.get_user_by_email(db, email)
        if user and verify_password(password, user.hashed_password):
            await db.users.update_one(
                {"email": email},
                {"$set": {"last_login": datetime.utcnow()}}
            )
            return user
        return None
    
    @staticmethod
    async def update_user(db: AsyncIOMotorDatabase, user_id: str, **kwargs) -> Optional[User]:
        """Update user information."""
        try:
            uuid_obj = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            result = await db.users.update_one(
                {"id": str(uuid_obj)},
                {"$set": kwargs}
            )
            if result.modified_count > 0:
                user_data = await db.users.find_one({"id": str(uuid_obj)})
                return User(**user_data) if user_data else None
            return None
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    async def get_users(db: AsyncIOMotorDatabase = None, skip: int = 0, limit: int = 100, role: str = None) -> List[User]:
        """Get list of users with pagination using Beanie ODM."""
        try:
            query = User.find()
            if role:
                query = User.find(User.role == role)
            
            users = await query.skip(skip).limit(limit).to_list()
            return users
        except Exception as e:
            logger.error(f"Error retrieving users: {e}")
            return []

class EmployerService:
    @staticmethod
    async def create_employer(db: AsyncIOMotorDatabase, employer_data: Dict[str, Any], user_id: str = None) -> Employer:
        """Create a new employer profile."""
        try:
            if user_id:
                uuid_obj = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
                employer_data['user_id'] = str(uuid_obj)
            
            # Use raw MongoDB driver instead of Beanie for now
            employer_dict = employer_data.copy()
            result = await db.employers.insert_one(employer_dict)
            employer_dict["_id"] = result.inserted_id
            
            # Convert back to Employer model for return
            return Employer(**employer_dict)
        except (ValueError, TypeError) as e:
            logger.error(f"Error creating employer: {e}")
            return None
    
    @staticmethod
    async def get_employer_by_user_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[Employer]:
        """Get employer by user ID."""
        try:
            uuid_obj = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            employer_data = await db.employers.find_one({"user_id": str(uuid_obj)})
            # Return raw dict instead of Employer model to avoid Beanie initialization
            return employer_data
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    async def get_employer_by_id(db: AsyncIOMotorDatabase, employer_id: str) -> Optional[Employer]:
        """Get employer by ID."""
        try:
            uuid_obj = uuid.UUID(employer_id) if isinstance(employer_id, str) else employer_id
            employer_data = await db.employers.find_one({"id": str(uuid_obj)})
            return Employer(**employer_data) if employer_data else None
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    async def get_employers(db: AsyncIOMotorDatabase, search: str = None, skip: int = 0, limit: int = 50) -> List[Employer]:
        """Get list of employers with optional search."""
        filter_dict = {}
        if search:
            filter_dict["$or"] = [
                {"company_name": {"$regex": search, "$options": "i"}},
                {"industry": {"$regex": search, "$options": "i"}},
                {"location": {"$regex": search, "$options": "i"}}
            ]
        
        cursor = db.employers.find(filter_dict).skip(skip).limit(limit)
        employers_data = await cursor.to_list(length=limit)
        return [Employer(**employer_data) for employer_data in employers_data]
    
    @staticmethod
    async def update_employer(db: AsyncIOMotorDatabase, employer_id: str, employer_data: Dict[str, Any]) -> Optional[Employer]:
        """Update employer information."""
        try:
            uuid_obj = uuid.UUID(employer_id) if isinstance(employer_id, str) else employer_id
            result = await db.employers.update_one(
                {"id": str(uuid_obj)},
                {"$set": employer_data}
            )
            if result.modified_count > 0:
                employer_data = await db.employers.find_one({"id": str(uuid_obj)})
                return Employer(**employer_data) if employer_data else None
            return None
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    async def delete_employer(db: AsyncIOMotorDatabase, employer_id: str) -> bool:
        """Delete employer by ID."""
        try:
            uuid_obj = uuid.UUID(employer_id) if isinstance(employer_id, str) else employer_id
            result = await db.employers.delete_one({"id": str(uuid_obj)})
            return result.deleted_count > 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    async def find_or_create_employer(db: AsyncIOMotorDatabase, company_name: str, **kwargs) -> Employer:
        """Find existing employer by company name or create new one."""
        employer_data = await db.employers.find_one({"company_name": company_name})
        if not employer_data:
            employer_dict = {
                "company_name": company_name,
                **kwargs
            }
            employer = Employer(**employer_dict)
            employer_dict = employer.dict()
            result = await db.employers.insert_one(employer_dict)
            employer_dict["_id"] = result.inserted_id
            return Employer(**employer_dict)
        return Employer(**employer_data)

class JobPostService:
    @staticmethod
    async def create_job_post(db: AsyncIOMotorDatabase, employer_id: str, job_data: Dict[str, Any]) -> JobPost:
        """Create a new job post."""
        try:
            uuid_obj = uuid.UUID(employer_id) if isinstance(employer_id, str) else employer_id
            # Get employer info for denormalized company_name
            employer_data = await db.employers.find_one({"id": str(uuid_obj)})
            
            job_post_data = {
                'employer_id': str(uuid_obj),
                'company_name': employer_data.get('company_name') if employer_data else None,
                **job_data
            }
            job_post = JobPost(**job_post_data)
            job_post_dict = job_post.dict()
            result = await db.job_posts.insert_one(job_post_dict)
            job_post_dict["_id"] = result.inserted_id
            return JobPost(**job_post_dict)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    async def get_job_post_by_id(db: AsyncIOMotorDatabase, job_id: int) -> Optional[JobPost]:
        """Get job post by ID."""
        job_post_data = await db.job_posts.find_one({"id": job_id})
        return JobPost(**job_post_data) if job_post_data else None
    
    @staticmethod
    async def get_job_posts(db: AsyncIOMotorDatabase, skip: int = 0, limit: int = 12, 
                     search: str = None, job_type: str = None, 
                     location: str = None, status: str = 'active') -> List[JobPost]:
        """Get list of job posts with filters."""
        filter_dict = {}
        
        if status is not None:
            filter_dict["status"] = status
        
        if search:
            filter_dict["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
                {"company_name": {"$regex": search, "$options": "i"}}
            ]
        
        if job_type:
            filter_dict["job_type"] = job_type
        
        if location:
            location_filter = {
                "$or": [
                    {"location_city": {"$regex": location, "$options": "i"}},
                    {"location_state": {"$regex": location, "$options": "i"}},
                    {"location_country": {"$regex": location, "$options": "i"}}
                ]
            }
            if "$or" in filter_dict:
                filter_dict = {"$and": [filter_dict, location_filter]}
            else:
                filter_dict.update(location_filter)
        
        cursor = db.job_posts.find(filter_dict).sort("created_at", -1).skip(skip).limit(limit)
        job_posts_data = await cursor.to_list(length=limit)
        return [JobPost(**job_post_data) for job_post_data in job_posts_data]
    
    @staticmethod
    async def get_job_posts_by_employer(db: AsyncIOMotorDatabase, employer_id: str, skip: int = 0, limit: int = 50) -> List[JobPost]:
        """Get job posts by employer."""
        try:
            uuid_obj = uuid.UUID(employer_id) if isinstance(employer_id, str) else employer_id
            cursor = db.job_posts.find({"employer_id": str(uuid_obj)}).skip(skip).limit(limit)
            job_posts_data = await cursor.to_list(length=limit)
            return [JobPost(**job_post_data) for job_post_data in job_posts_data]
        except (ValueError, TypeError):
            return []
    
    @staticmethod
    async def update_job_post(db: AsyncIOMotorDatabase, job_id: int, **kwargs) -> Optional[JobPost]:
        """Update job post."""
        result = await db.job_posts.update_one(
            {"id": job_id},
            {"$set": kwargs}
        )
        if result.modified_count > 0:
            job_post_data = await db.job_posts.find_one({"id": job_id})
            return JobPost(**job_post_data) if job_post_data else None
        return None
    
    @staticmethod
    async def increment_view_count(db: AsyncIOMotorDatabase, job_id: int):
        """Increment view count for a job post."""
        await db.job_posts.update_one(
            {"id": job_id},
            {"$inc": {"views_count": 1}}
        )

class JobApplicationService:
    @staticmethod
    async def create_application(db: AsyncIOMotorDatabase, job_post_id: int, job_seeker_id: int, 
                          application_data: Dict[str, Any]) -> JobApplication:
        """Create a new job application."""
        try:
            # Check if application already exists
            existing = await db.job_applications.find_one({
                "job_post_id": job_post_id,
                "job_seeker_id": job_seeker_id
            })
            
            if existing:
                raise ValueError("Application already exists for this job")
            
            application_dict = {
                "job_post_id": job_post_id,
                "job_seeker_id": job_seeker_id,
                **application_data
            }
            application = JobApplication(**application_dict)
            application_dict = application.dict()
            result = await db.job_applications.insert_one(application_dict)
            application_dict["_id"] = result.inserted_id
            
            # Increment applications count on job post
            await db.job_posts.update_one(
                {"id": job_post_id},
                {"$inc": {"applications_count": 1}}
            )
            
            return JobApplication(**application_dict)
        except Exception as e:
            raise e
    
    @staticmethod
    async def get_applications_by_job_seeker(db: AsyncIOMotorDatabase, job_seeker_id: int, 
                                     skip: int = 0, limit: int = 50) -> List[JobApplication]:
        """Get applications by job seeker."""
        cursor = db.job_applications.find({"job_seeker_id": job_seeker_id}).skip(skip).limit(limit)
        applications_data = await cursor.to_list(length=limit)
        return [JobApplication(**app_data) for app_data in applications_data]
    
    @staticmethod
    async def get_applications_by_job_post(db: AsyncIOMotorDatabase, job_post_id: int, 
                                   skip: int = 0, limit: int = 50) -> List[JobApplication]:
        """Get applications for a job post."""
        cursor = db.job_applications.find({"job_post_id": job_post_id}).skip(skip).limit(limit)
        applications_data = await cursor.to_list(length=limit)
        return [JobApplication(**app_data) for app_data in applications_data]
    
    @staticmethod
    async def update_application_status(db: AsyncIOMotorDatabase, application_id: int, status: str, 
                                notes: str = None) -> Optional[JobApplication]:
        """Update application status."""
        update_data = {"status": status}
        if notes:
            update_data["notes"] = notes
            
        result = await db.job_applications.update_one(
            {"id": application_id},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            application_data = await db.job_applications.find_one({"id": application_id})
            return JobApplication(**application_data) if application_data else None
        return None

class JobSeekerService:
    @staticmethod
    async def create_job_seeker(db: AsyncIOMotorDatabase = None, user_id: str = None, profile_data: Dict[str, Any] = None) -> JobSeeker:
        """Create a new job seeker profile using Beanie ODM."""
        from backend.models.mongodb_models import JobSeeker
        from bson import ObjectId
        
        try:
            # Convert string to ObjectId
            object_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
            
            job_seeker_data = {
                'user_id': object_id,
                **(profile_data or {})
            }
            job_seeker = JobSeeker(**job_seeker_data)
            await job_seeker.insert()
            return job_seeker
        except Exception as e:
            raise e
    
    @staticmethod
    async def get_job_seeker_by_user_id(db: AsyncIOMotorDatabase = None, user_id: str = None) -> Optional[JobSeeker]:
        """Get job seeker by user ID using Beanie ODM."""
        from backend.models.mongodb_models import JobSeeker
        from bson import ObjectId
        
        try:
            object_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
            job_seeker = await JobSeeker.find_one({"user_id": object_id})
            return job_seeker
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    async def update_job_seeker(db: AsyncIOMotorDatabase = None, job_seeker_id: ObjectId = None, **kwargs) -> Optional[JobSeeker]:
        """Update job seeker profile using Beanie ODM."""
        from backend.models.mongodb_models import JobSeeker
        
        job_seeker = await JobSeeker.get(job_seeker_id)
        if job_seeker:
            for key, value in kwargs.items():
                setattr(job_seeker, key, value)
            await job_seeker.save()
            return job_seeker
        return None
    
    @staticmethod
    async def get_job_seekers(db: AsyncIOMotorDatabase = None, search: str = None, skip: int = 0, limit: int = 50) -> List[JobSeeker]:
        """Get job seekers with optional search and pagination using Beanie ODM."""
        from backend.models.mongodb_models import JobSeeker
        
        query = JobSeeker.find()
        
        if search:
            query = JobSeeker.find({
                "$or": [
                    {"skills": {"$regex": search, "$options": "i"}},
                    {"experience_level": {"$regex": search, "$options": "i"}},
                    {"preferred_locations": {"$regex": search, "$options": "i"}}
                ]
            })
        
        job_seekers = await query.skip(skip).limit(limit).to_list()
        return job_seekers

class SystemService:
    @staticmethod
    async def get_setting(db: AsyncIOMotorDatabase, key: str) -> Optional[str]:
        """Get system setting value."""
        setting_data = await db.system_settings.find_one({"key": key})
        return setting_data.get("value") if setting_data else None
    
    @staticmethod
    async def set_setting(db: AsyncIOMotorDatabase, key: str, value: str, description: str = None, 
                   data_type: str = 'string', is_public: bool = False) -> Dict[str, Any]:
        """Set system setting."""
        setting_data = await db.system_settings.find_one({"key": key})
        
        if setting_data:
            update_data = {
                "value": value,
                "data_type": data_type,
                "is_public": is_public,
                "updated_at": datetime.utcnow()
            }
            if description:
                update_data["description"] = description
                
            await db.system_settings.update_one(
                {"key": key},
                {"$set": update_data}
            )
            updated_data = await db.system_settings.find_one({"key": key})
            return updated_data
        else:
            setting_dict = {
                "key": key,
                "value": value,
                "description": description,
                "data_type": data_type,
                "is_public": is_public
            }
            result = await db.system_settings.insert_one(setting_dict)
            setting_dict["_id"] = result.inserted_id
            return setting_dict
    
    @staticmethod
    async def log_admin_action(db: AsyncIOMotorDatabase, admin_user_id: str, action: str, 
                        target_table: str = None, target_id: str = None,
                        old_values: Dict = None, new_values: Dict = None,
                        ip_address: str = None, user_agent: str = None):
        """Log admin action."""
        log_entry_dict = {
            "admin_user_id": admin_user_id,
            "action": action,
            "target_table": target_table,
            "target_id": target_id,
            "old_values": json.dumps(old_values) if old_values else None,
            "new_values": json.dumps(new_values) if new_values else None,
            "ip_address": ip_address,
            "user_agent": user_agent
        }
        # log_entry = AdminLog(**log_entry_dict)
        # log_entry_dict = log_entry.dict()
        await db.admin_logs.insert_one(log_entry_dict)

class ScraperConfigService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def get_config(self, config_id: int) -> Optional[ScraperConfig]:
        config_data = await self.db.scraper_configs.find_one({"id": config_id})
        return ScraperConfig(**config_data) if config_data else None

    async def get_all_configs(self) -> List[ScraperConfig]:
        cursor = self.db.scraper_configs.find({})
        configs_data = await cursor.to_list(length=None)
        return [ScraperConfig(**config_data) for config_data in configs_data]

    async def get_active_configs(self) -> List[ScraperConfig]:
        cursor = self.db.scraper_configs.find({"is_active": True})
        configs_data = await cursor.to_list(length=None)
        return [ScraperConfig(**config_data) for config_data in configs_data]

    async def create_config(self, config_data: dict) -> ScraperConfig:
        config = ScraperConfig(**config_data)
        config_dict = config.dict()
        result = await self.db.scraper_configs.insert_one(config_dict)
        config_dict["_id"] = result.inserted_id
        return ScraperConfig(**config_dict)

    async def update_config(self, config_id: int, config_data: dict) -> Optional[ScraperConfig]:
        config_data["updated_at"] = datetime.utcnow()
        result = await self.db.scraper_configs.update_one(
            {"id": config_id},
            {"$set": config_data}
        )
        if result.modified_count > 0:
            updated_data = await self.db.scraper_configs.find_one({"id": config_id})
            return ScraperConfig(**updated_data) if updated_data else None
        return None

    async def delete_config(self, config_id: int) -> bool:
        result = await self.db.scraper_configs.delete_one({"id": config_id})
        return result.deleted_count > 0

class ScraperLogService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def get_log(self, log_id: int) -> Optional[ScraperLog]:
        log_data = await self.db.scraper_logs.find_one({"id": log_id})
        return ScraperLog(**log_data) if log_data else None

    async def get_logs_by_config(self, config_id: int) -> List[ScraperLog]:
        cursor = self.db.scraper_logs.find({"scraper_config_id": config_id})
        logs_data = await cursor.to_list(length=None)
        return [ScraperLog(**log_data) for log_data in logs_data]

    async def get_recent_logs(self, limit: int = 100) -> List[ScraperLog]:
        cursor = self.db.scraper_logs.find({}).sort("created_at", -1).limit(limit)
        logs_data = await cursor.to_list(length=limit)
        return [ScraperLog(**log_data) for log_data in logs_data]

    async def create_log(self, log_data: dict) -> ScraperLog:
        log = ScraperLog(**log_data)
        log_dict = log.dict()
        result = await self.db.scraper_logs.insert_one(log_dict)
        log_dict["_id"] = result.inserted_id
        return ScraperLog(**log_dict)

    async def update_log(self, log_id: int, log_data: dict) -> Optional[ScraperLog]:
        log_data["updated_at"] = datetime.utcnow()
        result = await self.db.scraper_logs.update_one(
            {"id": log_id},
            {"$set": log_data}
        )
        if result.modified_count > 0:
            updated_data = await self.db.scraper_logs.find_one({"id": log_id})
            return ScraperLog(**updated_data) if updated_data else None
        return None

    async def delete_log(self, log_id: int) -> bool:
        result = await self.db.scraper_logs.delete_one({"id": log_id})
        return result.deleted_count > 0

class ScraperMemoryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def get_memory(self, memory_id: int) -> Optional[Dict[str, Any]]:
        memory_data = await self.db.scraper_memories.find_one({"id": memory_id})
        return memory_data if memory_data else None

    async def get_memory_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        memory_data = await self.db.scraper_memories.find_one({"name": name})
        return memory_data if memory_data else None

    async def get_all_memories(self) -> List[Dict[str, Any]]:
        cursor = self.db.scraper_memories.find({})
        memories_data = await cursor.to_list(length=None)
        return memories_data

    async def get_active_memories(self) -> List[Dict[str, Any]]:
        cursor = self.db.scraper_memories.find({"is_active": True})
        memories_data = await cursor.to_list(length=None)
        return memories_data

    async def create_memory(self, memory_data: dict) -> Dict[str, Any]:
        result = await self.db.scraper_memories.insert_one(memory_data)
        memory_data["_id"] = result.inserted_id
        return memory_data

    async def update_memory(self, memory_id: int, memory_data: dict) -> Optional[Dict[str, Any]]:
        memory_data["updated_at"] = datetime.utcnow()
        result = await self.db.scraper_memories.update_one(
            {"id": memory_id},
            {"$set": memory_data}
        )
        if result.modified_count > 0:
            updated_data = await self.db.scraper_memories.find_one({"id": memory_id})
            return updated_data if updated_data else None
        return None

    async def delete_memory(self, memory_id: int) -> bool:
        result = await self.db.scraper_memories.delete_one({"id": memory_id})
        return result.deleted_count > 0

    async def increment_usage(self, memory_id: int) -> Optional[Dict[str, Any]]:
        result = await self.db.scraper_memories.update_one(
            {"id": memory_id},
            {
                "$inc": {"usage_count": 1},
                "$set": {"last_used_at": datetime.utcnow()}
            }
        )
        if result.modified_count > 0:
            updated_data = await self.db.scraper_memories.find_one({"id": memory_id})
            return updated_data if updated_data else None
        return None