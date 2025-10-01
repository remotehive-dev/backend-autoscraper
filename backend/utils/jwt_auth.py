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
        secret_key = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY")
        if not secret_key:
            raise ValueError("JWT_SECRET_KEY or SECRET_KEY environment variable is required")
        
        return cls(
            secret_key=secret_key,
            algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            access_token_expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "30")),
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
            # Remove 'Bearer ' prefix if present
            if token.startswith('Bearer '):
                token = token[7:]
            
            options = {"verify_exp": verify_exp}
            
            payload = jwt.decode(
                token, 
                self.config.secret_key, 
                algorithms=[self.config.algorithm],
                audience=self.config.audience,
                issuer=self.config.issuer,
                options=options
            )
            
            logger.debug(f"Successfully decoded token for subject: {payload.get('sub')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise TokenExpiredError("Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise TokenInvalidError(f"Invalid token: {e}")
        except Exception as e:
            logger.error(f"Failed to decode token: {e}")
            raise JWTError(f"Failed to decode token: {e}")
    
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
    
    def is_token_expired(self, token: str) -> bool:
        """Check if a token is expired"""
        try:
            payload = self.decode_token(token, verify_exp=False)
            exp = payload.get("exp")
            if exp:
                return datetime.utcnow().timestamp() > exp
            return True
        except JWTError:
            return True
    
    def refresh_access_token(self, refresh_token: str, user_data: Optional[Dict[str, Any]] = None) -> str:
        """Create a new access token using a refresh token"""
        try:
            payload = self.decode_token(refresh_token)
            
            # Verify it's a refresh token
            if payload.get("type") != TokenType.REFRESH.value:
                raise TokenInvalidError("Token is not a refresh token")
            
            subject = payload.get("sub")
            if not subject:
                raise TokenInvalidError("Token missing subject")
            
            # Create new access token
            return self.create_access_token(subject, user_data)
            
        except JWTError:
            raise
        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise JWTError(f"Failed to refresh access token: {e}")


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