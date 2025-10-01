from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
# from bson import ObjectId  # Removed to fix Pydantic schema generation
from datetime import datetime, timedelta
from loguru import logger
import json
import asyncio
from collections import defaultdict

from backend.schemas.admin import (
    AdminLogCreate, DashboardStats, UserSuspensionCreate, 
    AnnouncementCreate, ReportCreate, ReportUpdate, 
    AnalyticsFilter, DailyStats, SystemHealthCheck,
    BulkActionRequest, BulkActionResult, ExportRequest,
    AdminNotificationCreate, UserActivitySummary
)
# MongoDB models are now handled as dictionaries
from backend.core.config import settings

class AdminService:
    """Service class for admin operations using local database"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.logger = logger
    
    async def log_admin_action(
        self, 
        admin_user_id: str, 
        log_data: AdminLogCreate, 
        ip_address: str = None
    ) -> Optional[Dict[str, Any]]:
        """Log admin actions for audit trail"""
        try:
            # Create admin log entry
            import uuid
            log_entry = {
                "_id": str(uuid.uuid4()),
                "admin_user_id": admin_user_id,
                "action": log_data.action,
                "target_table": log_data.target_table,
                "target_id": log_data.target_id,
                "old_values": log_data.old_values,
                "new_values": log_data.new_values,
                "ip_address": ip_address,
                "user_agent": log_data.user_agent,
                "notes": getattr(log_data, 'notes', None),
                "created_at": datetime.utcnow()
            }
            
            result = await self.db.admin_logs.insert_one(log_entry)
            
            self.logger.info(f"Admin action logged: {log_data.action} by {admin_user_id}")
            return {
                "id": log_entry["_id"],
                "action": log_entry["action"],
                "created_at": log_entry["created_at"].isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to log admin action: {str(e)}")
            return None
    
    async def get_dashboard_stats(self) -> DashboardStats:
        """Get comprehensive dashboard statistics"""
        try:
            # Get user statistics
            total_users = await self.db.users.count_documents({})
            active_users = await self.db.users.count_documents({'is_active': True})
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            new_users_today = await self.db.users.count_documents(
                {'created_at': {'$gte': today_start}}
            )
            
            # Get weekly user statistics
            week_ago = datetime.now() - timedelta(days=7)
            new_users_this_week = await self.db.users.count_documents(
                {'created_at': {'$gte': week_ago}}
            )
            
            # Get job statistics
            total_jobs = await self.db.job_posts.count_documents({})
            active_jobs = await self.db.job_posts.count_documents({'status': 'active'})
            new_jobs_today = await self.db.job_posts.count_documents(
                {'created_at': {'$gte': today_start}}
            )
            
            # Get weekly job statistics
            new_jobs_this_week = await self.db.job_posts.count_documents(
                {'created_at': {'$gte': week_ago}}
            )
            
            # Get application statistics
            total_applications = await self.db.job_applications.count_documents({})
            pending_applications = await self.db.job_applications.count_documents(
                {'status': 'pending'}
            )
            new_applications_today = await self.db.job_applications.count_documents(
                {'created_at': {'$gte': today_start}}
            )
            
            # Calculate conversion rate (applications to jobs ratio)
            conversion_rate = (total_applications / total_jobs * 100) if total_jobs > 0 else 0
            
            # Mock revenue for now (would come from payment system)
            revenue_this_month = 0.0  # TODO: Implement actual revenue calculation
            
            # Mock response time (would come from monitoring system)
            avg_response_time = 150.0  # milliseconds
            
            return DashboardStats(
                total_users=total_users,
                active_users=active_users,
                total_jobs=total_jobs,
                active_jobs=active_jobs,
                total_applications=total_applications,
                pending_applications=pending_applications,
                revenue_this_month=revenue_this_month,
                new_users_this_week=new_users_this_week,
                new_jobs_this_week=new_jobs_this_week,
                conversion_rate=round(conversion_rate, 2),
                avg_response_time=avg_response_time
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get dashboard stats: {str(e)}")
            return DashboardStats(
                total_users=0, active_users=0, total_jobs=0, active_jobs=0,
                total_applications=0, pending_applications=0, revenue_this_month=0.0,
                new_users_this_week=0, new_jobs_this_week=0, conversion_rate=0.0,
                avg_response_time=0.0
            )
    
    async def suspend_user(
        self, 
        user_id: str, 
        suspension_data: UserSuspensionCreate, 
        admin_user_id: str
    ) -> bool:
        """Suspend a user account"""
        try:
            # Get user from MongoDB
            user = await self.db.users.find_one({"_id": user_id})
            if not user:
                return False
            
            # Update user status
            old_values = {"is_active": user.get("is_active", True)}
            result = await self.db.users.update_one(
                {"_id": user_id},
                {"$set": {"is_active": False}}
            )
            
            if result.modified_count == 0:
                return False
            
            # Log the action
            await self.log_admin_action(
                admin_user_id,
                AdminLogCreate(
                    action="suspend_user",
                    target_table="users",
                    target_id=user_id,
                    old_values=old_values,
                    new_values={"is_active": False},
                    notes=suspension_data.reason if hasattr(suspension_data, 'reason') else None
                )
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to suspend user {user_id}: {str(e)}")
            return False
    
    async def unsuspend_user(self, user_id: str, admin_user_id: str) -> bool:
        """Unsuspend a user account"""
        try:
            # Get user from MongoDB
            user = await self.db.users.find_one({"_id": user_id})
            if not user:
                return False
            
            # Update user status
            old_values = {"is_active": user.get("is_active", False)}
            result = await self.db.users.update_one(
                {"_id": user_id},
                {"$set": {"is_active": True}}
            )
            
            if result.modified_count == 0:
                return False
            
            # Log the action
            await self.log_admin_action(
                admin_user_id,
                AdminLogCreate(
                    action="unsuspend_user",
                    target_table="users",
                    target_id=user_id,
                    old_values=old_values,
                    new_values={"is_active": True}
                )
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unsuspend user {user_id}: {str(e)}")
            return False
    
    async def get_system_health(self) -> SystemHealthCheck:
        """Get system health status"""
        try:
            # Check database connectivity
            db_healthy = True
            db_response_time = 0.0
            try:
                # Test MongoDB connection with a simple ping and measure response time
                import time
                start_time = time.time()
                await self.db.command('ping')
                db_response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            except:
                db_healthy = False
                db_response_time = 999.0  # High response time indicates failure
            
            # Determine overall system status
            if db_healthy and db_response_time < 100:
                status = "healthy"
            elif db_healthy and db_response_time < 500:
                status = "warning"
            else:
                status = "critical"
            
            return SystemHealthCheck(
                status=status,
                database_status="healthy" if db_healthy else "error",
                redis_status="unknown",  # Would need Redis connection check
                api_response_time=db_response_time,
                memory_usage=0.0,    # Would need psutil for real memory usage
                cpu_usage=0.0,       # Would need psutil for real CPU usage
                disk_usage=0.0,      # Would need psutil for real disk usage
                active_connections=1,  # Placeholder - would need real connection count
                error_rate=0.0,      # Would need error tracking
                uptime="0d 0h 0m",   # Would need to track app start time
                last_backup=None     # Would need backup system integration
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get system health: {str(e)}")
            return SystemHealthCheck(
                status="critical",
                database_status="error",
                redis_status="unknown",
                api_response_time=999.0,
                memory_usage=0.0,
                cpu_usage=0.0,
                disk_usage=0.0,
                active_connections=0,
                error_rate=100.0,
                uptime="0d 0h 0m",
                last_backup=None
            )
    
    async def get_user_activity_summary(
        self, 
        user_id: str
    ) -> Optional[UserActivitySummary]:
        """Get user activity summary"""
        try:
            # Get user from MongoDB
            user = await self.db.users.find_one({"_id": user_id})
            if not user:
                return None
            
            # Get user's job applications
            applications = await self.db.job_applications.find(
                {"applicant_id": user_id}
            ).to_list(length=None)
            
            # Get user's job posts (if employer)
            job_posts = []
            if user.get("role") in ['EMPLOYER', 'ADMIN', 'SUPER_ADMIN']:
                job_posts = await self.db.job_posts.find(
                    {"employer_id": user_id}
                ).to_list(length=None)
            
            return UserActivitySummary(
                user_id=user_id,
                email=user.get("email"),
                full_name=user.get("full_name"),
                role=user.get("role"),
                total_applications=len(applications),
                total_job_posts=len(job_posts),
                last_login=user.get("last_login"),
                account_created=user.get("created_at"),
                is_active=user.get("is_active", True)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get user activity summary for {user_id}: {str(e)}")
            return None
    
    async def cleanup_expired_data(self) -> Dict[str, int]:
        """Clean up expired data from the database"""
        try:
            cleanup_results = {
                "expired_jobs": 0,
                "old_logs": 0,
                "inactive_sessions": 0
            }
            
            # Clean up expired job posts
            now = datetime.now()
            expired_jobs_result = await self.db.job_posts.update_many(
                {
                    "expires_at": {"$lt": now},
                    "status": {"$ne": "expired"}
                },
                {"$set": {"status": "expired"}}
            )
            
            cleanup_results["expired_jobs"] = expired_jobs_result.modified_count
            
            # Clean up old admin logs (older than 1 year)
            old_date = datetime.now() - timedelta(days=365)
            old_logs_result = await self.db.admin_logs.delete_many(
                {"created_at": {"$lt": old_date}}
            )
            
            cleanup_results["old_logs"] = old_logs_result.deleted_count
            
            self.logger.info(f"Cleanup completed: {cleanup_results}")
            return cleanup_results
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired data: {str(e)}")
            self.db.rollback()
            return {"expired_jobs": 0, "old_logs": 0, "inactive_sessions": 0}