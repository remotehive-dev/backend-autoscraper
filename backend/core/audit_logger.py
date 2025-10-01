from datetime import datetime
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from loguru import logger
import json

class AuditEvent:
    """Audit event types for authentication and security events"""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    REGISTRATION = "registration"
    PASSWORD_RESET_REQUEST = "password_reset_request"
    PASSWORD_RESET_SUCCESS = "password_reset_success"
    PASSWORD_CHANGE = "password_change"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_BLACKLIST = "token_blacklist"
    OAUTH_LOGIN = "oauth_login"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    PERMISSION_DENIED = "permission_denied"
    ACCOUNT_LOCKED = "account_locked"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    ADMIN_ACTION = "admin_action"

class AuditLogger:
    """Comprehensive audit logging service for authentication and security events"""
    
    def __init__(self):
        self.collection_name = "audit_logs"
    
    async def log_event(
        self,
        db: AsyncIOMotorDatabase,
        event_type: str,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        risk_level: str = "low"
    ) -> str:
        """Log an audit event to the database and system logs"""
        
        audit_record = {
            "event_id": self._generate_event_id(),
            "event_type": event_type,
            "timestamp": datetime.utcnow(),
            "user_id": user_id,
            "user_email": user_email,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "risk_level": risk_level,
            "details": details or {},
            "session_info": {
                "created_at": datetime.utcnow().isoformat(),
                "source": "authentication_system"
            }
        }
        
        try:
            # Store in database
            collection = db[self.collection_name]
            result = await collection.insert_one(audit_record)
            audit_record["_id"] = str(result.inserted_id)
            
            # Log to system logger based on risk level
            log_message = self._format_log_message(audit_record)
            
            if risk_level == "high" or not success:
                logger.error(log_message)
            elif risk_level == "medium":
                logger.warning(log_message)
            else:
                logger.info(log_message)
            
            return audit_record["event_id"]
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {str(e)}")
            # Fallback to system logging only
            logger.error(f"AUDIT_FALLBACK: {json.dumps(audit_record, default=str)}")
            return audit_record["event_id"]
    
    async def log_login_attempt(
        self,
        db: AsyncIOMotorDatabase,
        email: str,
        ip_address: str,
        user_agent: str,
        success: bool,
        user_id: Optional[str] = None,
        failure_reason: Optional[str] = None
    ) -> str:
        """Log login attempt with specific details"""
        
        event_type = AuditEvent.LOGIN_SUCCESS if success else AuditEvent.LOGIN_FAILED
        risk_level = "low" if success else "medium"
        
        details = {
            "login_method": "email_password",
            "failure_reason": failure_reason
        }
        
        return await self.log_event(
            db=db,
            event_type=event_type,
            user_id=user_id,
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            details=details,
            risk_level=risk_level
        )
    
    async def log_registration(
        self,
        db: AsyncIOMotorDatabase,
        user_id: str,
        email: str,
        role: str,
        ip_address: str,
        user_agent: str,
        registration_method: str = "direct"
    ) -> str:
        """Log user registration event"""
        
        details = {
            "role": role,
            "registration_method": registration_method
        }
        
        return await self.log_event(
            db=db,
            event_type=AuditEvent.REGISTRATION,
            user_id=user_id,
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            details=details,
            risk_level="low"
        )
    
    async def log_password_reset_request(
        self,
        db: AsyncIOMotorDatabase,
        email: str,
        ip_address: str,
        user_agent: str,
        user_id: Optional[str] = None
    ) -> str:
        """Log password reset request"""
        
        return await self.log_event(
            db=db,
            event_type=AuditEvent.PASSWORD_RESET_REQUEST,
            user_id=user_id,
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            risk_level="medium"
        )
    
    async def log_password_reset_success(
        self,
        db: AsyncIOMotorDatabase,
        user_id: str,
        email: str,
        ip_address: str,
        user_agent: str
    ) -> str:
        """Log successful password reset"""
        
        return await self.log_event(
            db=db,
            event_type=AuditEvent.PASSWORD_RESET_SUCCESS,
            user_id=user_id,
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            risk_level="medium"
        )
    
    async def log_logout(
        self,
        db: AsyncIOMotorDatabase,
        user_id: str,
        email: str,
        ip_address: str,
        user_agent: str,
        logout_type: str = "manual"
    ) -> str:
        """Log user logout event"""
        
        details = {
            "logout_type": logout_type  # manual, token_expiry, admin_forced
        }
        
        return await self.log_event(
            db=db,
            event_type=AuditEvent.LOGOUT,
            user_id=user_id,
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            details=details,
            risk_level="low"
        )
    
    async def log_rate_limit_exceeded(
        self,
        db: AsyncIOMotorDatabase,
        ip_address: str,
        user_agent: str,
        endpoint: str,
        user_email: Optional[str] = None
    ) -> str:
        """Log rate limit exceeded event"""
        
        details = {
            "endpoint": endpoint,
            "limit_type": "rate_limit"
        }
        
        return await self.log_event(
            db=db,
            event_type=AuditEvent.RATE_LIMIT_EXCEEDED,
            user_email=user_email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            details=details,
            risk_level="medium"
        )
    
    async def log_permission_denied(
        self,
        db: AsyncIOMotorDatabase,
        user_id: str,
        email: str,
        ip_address: str,
        user_agent: str,
        resource: str,
        required_permission: str
    ) -> str:
        """Log permission denied event"""
        
        details = {
            "resource": resource,
            "required_permission": required_permission
        }
        
        return await self.log_event(
            db=db,
            event_type=AuditEvent.PERMISSION_DENIED,
            user_id=user_id,
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            details=details,
            risk_level="high"
        )
    
    async def log_admin_action(
        self,
        db: AsyncIOMotorDatabase,
        admin_user_id: str,
        admin_email: str,
        action: str,
        target_user_id: Optional[str] = None,
        target_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log administrative actions"""
        
        admin_details = {
            "action": action,
            "target_user_id": target_user_id,
            "target_email": target_email,
            **(details or {})
        }
        
        return await self.log_event(
            db=db,
            event_type=AuditEvent.ADMIN_ACTION,
            user_id=admin_user_id,
            user_email=admin_email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            details=admin_details,
            risk_level="medium"
        )
    
    async def get_audit_logs(
        self,
        db: AsyncIOMotorDatabase,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> list:
        """Retrieve audit logs with filtering"""
        
        query = {}
        
        if user_id:
            query["user_id"] = user_id
        
        if event_type:
            query["event_type"] = event_type
        
        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date
        
        try:
            collection = db[self.collection_name]
            cursor = collection.find(query).sort("timestamp", -1).limit(limit)
            logs = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string for JSON serialization
            for log in logs:
                log["_id"] = str(log["_id"])
            
            return logs
            
        except Exception as e:
            logger.error(f"Failed to retrieve audit logs: {str(e)}")
            return []
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        import uuid
        return str(uuid.uuid4())
    
    def _format_log_message(self, audit_record: Dict[str, Any]) -> str:
        """Format audit record for system logging"""
        
        return (
            f"AUDIT: {audit_record['event_type']} | "
            f"User: {audit_record.get('user_email', 'N/A')} | "
            f"IP: {audit_record.get('ip_address', 'N/A')} | "
            f"Success: {audit_record['success']} | "
            f"Risk: {audit_record['risk_level']} | "
            f"Details: {json.dumps(audit_record.get('details', {}))}"
        )

# Global audit logger instance
_audit_logger = None

def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger

# Convenience functions
async def log_authentication_event(
    db: AsyncIOMotorDatabase,
    event_type: str,
    user_email: str,
    ip_address: str,
    user_agent: str,
    success: bool = True,
    user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> str:
    """Convenience function for logging authentication events"""
    audit_logger = get_audit_logger()
    return await audit_logger.log_event(
        db=db,
        event_type=event_type,
        user_id=user_id,
        user_email=user_email,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        details=details
    )