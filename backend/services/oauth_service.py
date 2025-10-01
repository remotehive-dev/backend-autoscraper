from typing import Optional, Dict, Any
import httpx
import jwt
from datetime import datetime, timedelta
from urllib.parse import urlencode, parse_qs
import secrets
import logging
from backend.core.config import settings
from backend.models.mongodb_models import User, UserRole
from backend.database.database import get_db_session
from backend.services.lead_service import LeadService
from beanie import PydanticObjectId

logger = logging.getLogger(__name__)

class OAuthService:
    """Service for handling Google OAuth authentication flow"""
    
    def __init__(self):
        self.client_id = settings.GOOGLE_OAUTH_CLIENT_ID
        self.client_secret = settings.GOOGLE_OAUTH_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI
        self.scopes = settings.GOOGLE_OAUTH_SCOPES
        self.auth_url = "https://accounts.google.com/o/oauth2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        
    def generate_auth_url(self, state: Optional[str] = None, role: Optional[str] = None) -> str:
        """Generate Google OAuth authorization URL with optional role parameter"""
        if not state:
            state = secrets.token_urlsafe(32)
            
        # Include role in state if provided
        if role:
            state = f"{state}|role:{role}"
            
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "state": state
        }
        
        return f"{self.auth_url}?{urlencode(params)}"
    
    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        try:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(self.token_url, data=data)
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            raise Exception(f"Failed to exchange authorization code: {str(e)}")
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Google using access token"""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            async with httpx.AsyncClient() as client:
                response = await client.get(self.userinfo_url, headers=headers)
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"Error getting user info: {e}")
            raise Exception(f"Failed to get user information: {str(e)}")
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        try:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(self.token_url, data=data)
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"Error refreshing access token: {e}")
            raise Exception(f"Failed to refresh access token: {str(e)}")
    
    async def authenticate_or_create_user(self, user_info: Dict[str, Any], tokens: Dict[str, Any], role: Optional[str] = None) -> User:
        """Authenticate existing user or create new user from OAuth info with optional role"""
        try:
            email = user_info.get("email")
            if not email:
                raise Exception("Email not provided by OAuth provider")
            
            # Check if user already exists
            existing_user = await User.find_one(User.email == email)
            
            if existing_user:
                # Update OAuth tokens for existing user
                existing_user.oauth_access_token = tokens.get("access_token")
                existing_user.oauth_refresh_token = tokens.get("refresh_token")
                existing_user.oauth_token_expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
                existing_user.last_login = datetime.utcnow()
                await existing_user.save()
                
                # Update lead activity for existing user
                try:
                    lead_service = LeadService()
                    await lead_service.update_lead_activity(existing_user.email, "google_oauth_login")
                except Exception as e:
                    logger.warning(f"Failed to update lead activity for {email}: {e}")
                
                return existing_user
            else:
                # Determine user role
                user_role = UserRole.JOB_SEEKER  # Default role
                if role:
                    try:
                        if role.upper() == "EMPLOYER":
                            user_role = UserRole.EMPLOYER
                        elif role.upper() == "JOB_SEEKER":
                            user_role = UserRole.JOB_SEEKER
                    except Exception as e:
                        logger.warning(f"Invalid role '{role}' provided, using default JOB_SEEKER: {e}")
                
                # Create new user
                new_user = User(
                    email=email,
                    full_name=user_info.get("name", ""),
                    first_name=user_info.get("given_name", ""),
                    last_name=user_info.get("family_name", ""),
                    profile_picture=user_info.get("picture", ""),
                    is_verified=user_info.get("verified_email", False),
                    role=user_role,
                    oauth_provider="google",
                    oauth_id=user_info.get("id"),
                    oauth_access_token=tokens.get("access_token"),
                    oauth_refresh_token=tokens.get("refresh_token"),
                    oauth_token_expires_at=datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600)),
                    created_at=datetime.utcnow(),
                    last_login=datetime.utcnow()
                )
                await new_user.save()
                
                # Create role-specific profile
                try:
                    from backend.database.services import EmployerService, JobSeekerService
                    from backend.database.database import get_database
                    
                    db = await get_database()
                    
                    if user_role == UserRole.EMPLOYER:
                        # Create employer profile
                        employer_data = {
                            "company_name": f"{user_info.get('given_name', '')} {user_info.get('family_name', '')} Company",
                            "company_email": email,
                            "company_description": "New employer profile from OAuth",
                            "industry": "Not specified",
                            "company_size": "startup",
                            "location": "Not specified"
                        }
                        await EmployerService.create_employer(db, employer_data, str(new_user.id))
                        logger.info(f"Created employer profile for OAuth user: {email}")
                    else:
                        # Create job seeker profile
                        job_seeker_data = {
                            "experience_level": "entry",
                            "skills": [],
                            "preferred_job_types": ["full_time"],
                            "preferred_locations": ["Remote"],
                            "is_actively_looking": True
                        }
                        await JobSeekerService.create_job_seeker(db, str(new_user.id), job_seeker_data)
                        logger.info(f"Created job seeker profile for OAuth user: {email}")
                        
                except Exception as profile_error:
                    logger.warning(f"Failed to create profile for OAuth user: {profile_error}")
                
                # Create lead for new OAuth user
                try:
                    lead_service = LeadService()
                    await lead_service.create_lead_from_signup(
                        email=email,
                        name=user_info.get("name", ""),
                        role=user_role,
                        source="google_auth",
                        metadata={
                            "oauth_provider": "google",
                            "oauth_id": user_info.get("id"),
                            "verified_email": user_info.get("verified_email", False),
                            "profile_picture": user_info.get("picture", "")
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to create lead for OAuth user {email}: {e}")
                
                return new_user
                
        except Exception as e:
            logger.error(f"Error authenticating/creating user: {e}")
            raise Exception(f"Failed to authenticate or create user: {str(e)}")
    
    def generate_jwt_token(self, user: User) -> str:
        """Generate JWT token for authenticated user"""
        try:
            payload = {
                "user_id": str(user.id),
                "email": user.email,
                "role": user.role.value if user.role else "job_seeker",
                "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
                "iat": datetime.utcnow(),
                "iss": "remotehive",
                "sub": str(user.id)
            }
            
            return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)
            
        except Exception as e:
            logger.error(f"Error generating JWT token: {e}")
            raise Exception(f"Failed to generate JWT token: {str(e)}")
    
    async def validate_oauth_token(self, access_token: str) -> bool:
        """Validate OAuth access token with Google"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://www.googleapis.com/oauth2/v1/tokeninfo?access_token={access_token}"
                )
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"Error validating OAuth token: {e}")
            return False
    
    async def revoke_oauth_token(self, token: str) -> bool:
        """Revoke OAuth token"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://oauth2.googleapis.com/revoke?token={token}"
                )
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"Error revoking OAuth token: {e}")
            return False

# Global instance
oauth_service = OAuthService()