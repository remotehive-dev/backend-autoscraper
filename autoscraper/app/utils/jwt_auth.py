#!/usr/bin/env python3
"""
JWT Authentication Utilities
Provides consistent JWT token handling across RemoteHive services
"""

import jwt
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from loguru import logger
from dataclasses import dataclass
from enum import Enum


class TokenType(Enum):
    """JWT token types"""
    ACCESS = "access"
    REFRESH = "refresh"
    API = "api"
    SERVICE = "service"


@dataclass
class JWTConfig:
    """JWT configuration settings"""
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    issuer: str = "RemoteHive"
    audience: str = "RemoteHive-Services"
    
    @classmethod
    def from_env(cls) -> 'JWTConfig':
        """Create JWT config from environment variables"""
        # Import settings here to avoid circular imports
        from config.settings import get_settings
        settings = get_settings()
        
        return cls(
            secret_key=settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
            access_token_expire_minutes=settings.JWT_EXPIRE_MINUTES,
            refresh_token_expire_days=int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7")),
            issuer=os.getenv("JWT_ISSUER", "RemoteHive"),
            audience=os.getenv("JWT_AUDIENCE", "RemoteHive-Services")
        )


class JWTError(Exception):
    """Base JWT error"""
    pass


class TokenExpiredError(JWTError):
    """Token has expired"""
    pass


class TokenInvalidError(JWTError):
    """Token is invalid"""
    pass


class JWTManager:
    """JWT token manager for encoding and decoding tokens"""
    
    def __init__(self, config: Optional[JWTConfig] = None):
        self.config = config or JWTConfig.from_env()
        logger.info(f"JWT Manager initialized with algorithm: {self.config.algorithm}")
    
    def create_access_token(
        self, 
        subject: Union[str, int], 
        user_data: Optional[Dict[str, Any]] = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create an access token"""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.config.access_token_expire_minutes)
        
        payload = {
            "sub": str(subject),
            "exp": expire,
            "iat": datetime.utcnow(),
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "type": TokenType.ACCESS.value
        }
        
        # Add user data if provided
        if user_data:
            payload.update(user_data)
        
        try:
            token = jwt.encode(payload, self.config.secret_key, algorithm=self.config.algorithm)
            logger.debug(f"Created access token for subject: {subject}")
            return token
        except Exception as e:
            logger.error(f"Failed to create access token: {e}")
            raise JWTError(f"Failed to create access token: {e}")
    
    def create_refresh_token(
        self, 
        subject: Union[str, int],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a refresh token"""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.config.refresh_token_expire_days)
        
        payload = {
            "sub": str(subject),
            "exp": expire,
            "iat": datetime.utcnow(),
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "type": TokenType.REFRESH.value
        }
        
        try:
            token = jwt.encode(payload, self.config.secret_key, algorithm=self.config.algorithm)
            logger.debug(f"Created refresh token for subject: {subject}")
            return token
        except Exception as e:
            logger.error(f"Failed to create refresh token: {e}")
            raise JWTError(f"Failed to create refresh token: {e}")
    
    def create_service_token(
        self, 
        service_name: str,
        permissions: Optional[list] = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a service-to-service authentication token"""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=24)  # Service tokens last longer
        
        payload = {
            "sub": service_name,
            "exp": expire,
            "iat": datetime.utcnow(),
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "type": TokenType.SERVICE.value,
            "service": service_name,
            "permissions": permissions or []
        }
        
        try:
            token = jwt.encode(payload, self.config.secret_key, algorithm=self.config.algorithm)
            logger.debug(f"Created service token for: {service_name}")
            return token
        except Exception as e:
            logger.error(f"Failed to create service token: {e}")
            raise JWTError(f"Failed to create service token: {e}")
    
    def decode_token(self, token: str, verify_exp: bool = True) -> Dict[str, Any]:
        """Decode and verify a JWT token"""
        try:
            options = {"verify_exp": verify_exp}
            payload = jwt.decode(
                token, 
                self.config.secret_key, 
                algorithms=[self.config.algorithm],
                audience=self.config.audience,
                issuer=self.config.issuer,
                options=options
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise TokenInvalidError(f"Invalid token: {e}")
        except Exception as e:
            logger.error(f"Token decode error: {e}")
            raise JWTError(f"Token decode failed: {e}")
    
    def verify_token(self, token: str) -> bool:
        """Verify if a token is valid"""
        try:
            self.decode_token(token)
            return True
        except JWTError:
            return False
    
    def get_token_subject(self, token: str) -> Optional[str]:
        """Get the subject from a token without full verification"""
        try:
            payload = self.decode_token(token, verify_exp=False)
            return payload.get("sub")
        except JWTError:
            return None
    
    def get_token_type(self, token: str) -> Optional[TokenType]:
        """Get the token type"""
        try:
            payload = self.decode_token(token, verify_exp=False)
            token_type = payload.get("type")
            return TokenType(token_type) if token_type else None
        except (JWTError, ValueError):
            return None
    
    def refresh_access_token(self, refresh_token: str) -> str:
        """Create a new access token from a refresh token"""
        try:
            payload = self.decode_token(refresh_token)
            
            # Verify it's a refresh token
            if payload.get("type") != TokenType.REFRESH.value:
                raise TokenInvalidError("Invalid token type for refresh")
            
            subject = payload.get("sub")
            if not subject:
                raise TokenInvalidError("Missing subject in refresh token")
            
            # Create new access token
            return self.create_access_token(subject)
            
        except JWTError:
            raise
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            raise JWTError(f"Token refresh failed: {e}")
    
    def get_token_claims(self, token: str) -> Dict[str, Any]:
        """Get all claims from a token"""
        return self.decode_token(token, verify_exp=False)


# Global JWT manager instance
_jwt_manager = None


def get_jwt_manager() -> JWTManager:
    """Get the global JWT manager instance"""
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    return _jwt_manager


def create_access_token(subject: Union[str, int], user_data: Optional[Dict[str, Any]] = None) -> str:
    """Convenience function to create an access token"""
    return get_jwt_manager().create_access_token(subject, user_data)


def create_refresh_token(subject: Union[str, int]) -> str:
    """Convenience function to create a refresh token"""
    return get_jwt_manager().create_refresh_token(subject)


def create_service_token(service_name: str, permissions: Optional[list] = None) -> str:
    """Convenience function to create a service token"""
    return get_jwt_manager().create_service_token(service_name, permissions)


def decode_token(token: str) -> Dict[str, Any]:
    """Convenience function to decode a token"""
    return get_jwt_manager().decode_token(token)


def verify_token(token: str) -> bool:
    """Convenience function to verify a token"""
    return get_jwt_manager().verify_token(token)


def extract_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """Extract user information from a JWT token"""
    try:
        payload = decode_token(token)
        
        # Extract user information
        user_info = {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "username": payload.get("username"),
            "role": payload.get("role"),
            "permissions": payload.get("permissions", []),
            "token_type": payload.get("type")
        }
        
        # Remove None values
        return {k: v for k, v in user_info.items() if v is not None}
        
    except JWTError:
        return None


def get_authorization_header(token: str) -> Dict[str, str]:
    """Get authorization header for API requests"""
    return {"Authorization": f"Bearer {token}"}


def validate_service_token(token: str, required_service: Optional[str] = None) -> bool:
    """Validate a service-to-service token"""
    try:
        payload = decode_token(token)
        
        # Check if it's a service token
        if payload.get("type") != TokenType.SERVICE.value:
            return False
        
        # Check specific service if required
        if required_service and payload.get("service") != required_service:
            return False
        
        return True
        
    except JWTError:
        return False