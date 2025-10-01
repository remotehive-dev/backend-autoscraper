#!/usr/bin/env python3
"""
Token Blacklist Service
Manages blacklisted JWT tokens for security purposes
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Set
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.database.mongodb_models import UserSession
from backend.utils.jwt_auth import get_jwt_manager, JWTError


class TokenBlacklistService:
    """Service for managing blacklisted tokens"""
    
    def __init__(self):
        # In-memory cache for frequently accessed blacklisted tokens
        self._memory_blacklist: Set[str] = set()
        self._last_cleanup = datetime.utcnow()
        self._cleanup_interval = timedelta(hours=1)
    
    async def blacklist_token(self, db: AsyncIOMotorDatabase, token: str, user_id: str, reason: str = "logout") -> bool:
        """Blacklist a token by marking the associated session as inactive."""
        try:
            # Add to memory cache for immediate effect
            self._memory_blacklist.add(token)
            
            # Mark session as inactive in database
            result = await db["user_sessions"].update_one(
                {"access_token": token, "user_id": user_id},
                {"$set": {"is_active": False, "blacklisted_at": datetime.utcnow()}}
            )
            
            if result.modified_count > 0:
                logger.info(f"Token blacklisted for user {user_id}, reason: {reason}")
                return True
            else:
                # If no session found, still add to memory blacklist
                logger.warning(f"No active session found for token, but added to memory blacklist")
                return True
                
        except Exception as e:
            logger.error(f"Error blacklisting token: {e}")
            return False
    
    async def is_token_blacklisted(self, db: AsyncIOMotorDatabase, token: str) -> bool:
        """Check if a token is blacklisted."""
        try:
            # Check memory cache first for performance
            if token in self._memory_blacklist:
                return True
            
            # Check database for inactive sessions
            session = await db["user_sessions"].find_one({
                "access_token": token,
                "is_active": False
            })
            
            is_blacklisted = session is not None
            if is_blacklisted:
                # Add to memory cache for future checks
                self._memory_blacklist.add(token)
            
            return is_blacklisted
            
        except Exception as e:
            logger.error(f"Error checking token blacklist: {e}")
            # In case of error, assume token is valid to avoid blocking legitimate users
            return False
    
    async def blacklist_all_user_tokens(self, db: AsyncIOMotorDatabase, user_id: str, reason: str = "security") -> int:
        """
        Blacklist all active tokens for a user
        
        Args:
            db: Database connection
            user_id: User ID whose tokens to blacklist
            reason: Reason for blacklisting
        
        Returns:
            Number of tokens blacklisted
        """
        try:
            # Find all active sessions for the user
            active_sessions = await UserSession.find(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            ).to_list()
            
            blacklisted_count = 0
            
            for session in active_sessions:
                # Update session to inactive
                session.is_active = False
                session.last_activity = datetime.utcnow()
                await session.save()
                
                # Add to memory cache
                if session.session_token:
                    self._memory_blacklist.add(session.session_token)
                
                blacklisted_count += 1
            
            logger.info(f"Blacklisted {blacklisted_count} tokens for user {user_id}, reason: {reason}")
            return blacklisted_count
            
        except Exception as e:
            logger.error(f"Error blacklisting user tokens: {e}")
            return 0
    
    async def cleanup_expired_tokens(self, db: AsyncIOMotorDatabase) -> int:
        """
        Clean up expired blacklisted tokens from database and memory
        
        Args:
            db: Database connection
        
        Returns:
            Number of tokens cleaned up
        """
        try:
            now = datetime.utcnow()
            
            # Skip if cleanup was done recently
            if now - self._last_cleanup < self._cleanup_interval:
                return 0
            
            # Remove expired sessions from database
            result = await UserSession.find(
                UserSession.expires_at <= now,
                UserSession.is_active == False
            ).delete()
            
            cleaned_count = result.deleted_count if result else 0
            
            # Clear memory cache (will be rebuilt as needed)
            self._memory_blacklist.clear()
            
            self._last_cleanup = now
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired blacklisted tokens")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error during token cleanup: {e}")
            return 0
    
    async def get_blacklisted_tokens_count(self, db: AsyncIOMotorDatabase, user_id: Optional[str] = None) -> int:
        """
        Get count of blacklisted tokens
        
        Args:
            db: Database connection
            user_id: Optional user ID to filter by
        
        Returns:
            Number of blacklisted tokens
        """
        try:
            query = {"is_active": False}
            if user_id:
                query["user_id"] = user_id
            
            count = await UserSession.find(query).count()
            return count
            
        except Exception as e:
            logger.error(f"Error getting blacklisted tokens count: {e}")
            return 0
    
    def clear_memory_cache(self) -> None:
        """
        Clear the in-memory blacklist cache
        """
        self._memory_blacklist.clear()
        logger.debug("Token blacklist memory cache cleared")


# Global token blacklist service instance
_token_blacklist_service = None


def get_token_blacklist_service() -> TokenBlacklistService:
    """Get the global token blacklist service instance"""
    global _token_blacklist_service
    if _token_blacklist_service is None:
        _token_blacklist_service = TokenBlacklistService()
    return _token_blacklist_service


# Convenience functions
async def blacklist_token(db: AsyncIOMotorDatabase, token: str, reason: str = "logout") -> bool:
    """Convenience function to blacklist a token"""
    service = get_token_blacklist_service()
    return await service.blacklist_token(db, token, reason)


async def is_token_blacklisted(db: AsyncIOMotorDatabase, token: str) -> bool:
    """Convenience function to check if token is blacklisted"""
    service = get_token_blacklist_service()
    return await service.is_token_blacklisted(db, token)


async def blacklist_all_user_tokens(db: AsyncIOMotorDatabase, user_id: str, reason: str = "security") -> int:
    """Convenience function to blacklist all user tokens"""
    service = get_token_blacklist_service()
    return await service.blacklist_all_user_tokens(db, user_id, reason)