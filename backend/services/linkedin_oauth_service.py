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

class LinkedInOAuthService:
    """Service for handling LinkedIn OAuth authentication flow"""
    
    def __init__(self):
        self.client_id = settings.LINKEDIN_OAUTH_CLIENT_ID
        self.client_secret = settings.LINKEDIN_OAUTH_CLIENT_SECRET
        self.redirect_uri = settings.LINKEDIN_OAUTH_REDIRECT_URI
        self.scopes = settings.LINKEDIN_OAUTH_SCOPES
        self.auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        self.token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        self.userinfo_url = "https://api.linkedin.com/v2/people/~:(id,firstName,lastName,emailAddress,profilePicture(displayImage~:playableStreams))"
        self.email_url = "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))"
        
    def generate_auth_url(self, state: Optional[str] = None, role: Optional[str] = None) -> str:
        """Generate LinkedIn OAuth authorization URL with optional role parameter"""
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
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(self.token_url, data=data, headers=headers)
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            raise Exception(f"Failed to exchange authorization code: {str(e)}")
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from LinkedIn using access token"""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            async with httpx.AsyncClient() as client:
                # Get basic profile info
                profile_response = await client.get(self.userinfo_url, headers=headers)
                profile_response.raise_for_status()
                profile_data = profile_response.json()
                
                # Get email address
                email_response = await client.get(self.email_url, headers=headers)
                email_response.raise_for_status()
                email_data = email_response.json()
                
                # Extract email from response
                email = None
                if "elements" in email_data and len(email_data["elements"]) > 0:
                    email_element = email_data["elements"][0]
                    if "handle~" in email_element:
                        email = email_element["handle~"].get("emailAddress")
                
                # Format user info similar to Google OAuth response
                user_info = {
                    "id": profile_data.get("id"),
                    "email": email,
                    "name": f"{profile_data.get('firstName', {}).get('localized', {}).get('en_US', '')} {profile_data.get('lastName', {}).get('localized', {}).get('en_US', '')}".strip(),
                    "given_name": profile_data.get('firstName', {}).get('localized', {}).get('en_US', ''),
                    "family_name": profile_data.get('lastName', {}).get('localized', {}).get('en_US', ''),
                    "picture": self._extract_profile_picture(profile_data),
                    "verified_email": True  # LinkedIn emails are generally verified
                }
                
                return user_info
                
        except httpx.HTTPError as e:
            logger.error(f"Error getting user info: {e}")
            raise Exception(f"Failed to get user information: {str(e)}")
    
    def _extract_profile_picture(self, profile_data: Dict[str, Any]) -> str:
        """Extract profile picture URL from LinkedIn profile data"""
        try:
            profile_picture = profile_data.get("profilePicture", {})
            display_image = profile_picture.get("displayImage~", {})
            elements = display_image.get("elements", [])
            
            if elements:
                # Get the largest available image
                largest_image = max(elements, key=lambda x: x.get("data", {}).get("com.linkedin.digitalmedia.mediaartifact.StillImage", {}).get("storageSize", {}).get("width", 0))
                identifiers = largest_image.get("identifiers", [])
                if identifiers:
                    return identifiers[0].get("identifier", "")
            
            return ""
        except Exception as e:
            logger.warning(f"Error extracting profile picture: {e}")
            return ""
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token (LinkedIn doesn't provide refresh tokens)"""
        # LinkedIn OAuth 2.0 doesn't provide refresh tokens
        # Access tokens are valid for 60 days
        raise Exception("LinkedIn OAuth does not support refresh tokens")
    
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
                existing_user.oauth_token_expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 5184000))  # 60 days default
                existing_user.last_login = datetime.utcnow()
                await existing_user.save()
                
                # Update lead activity for existing user
                try:
                    lead_service = LeadService()
                    await lead_service.update_lead_activity(existing_user.email, "linkedin_oauth_login")
                except Exception as e:
                    logger.warning(f"Failed to update lead activity for {email}: {e}")
                
                return existing_user
            else:
                # Determine user role - support all RemoteHive roles
                user_role = UserRole.JOB_SEEKER  # Default role
                if role:
                    try:
                        role_upper = role.upper()
                        if role_upper == "EMPLOYER":
                            user_role = UserRole.EMPLOYER
                        elif role_upper == "JOB_SEEKER":
                            user_role = UserRole.JOB_SEEKER
                        elif role_upper == "GEEKWORKER":
                            user_role = UserRole.GEEK_WORKER
                        elif role_upper == "FREELANCER":
                            user_role = UserRole.FREELANCER
                    except Exception as e:
                        logger.warning(f"Invalid role '{role}' provided, using default JOB_SEEKER: {e}")
                
                # Create new user
                new_user = User(
                    email=email,
                    full_name=user_info.get("name", ""),
                    first_name=user_info.get("given_name", ""),
                    last_name=user_info.get("family_name", ""),
                    profile_picture=user_info.get("picture", ""),
                    is_verified=user_info.get("verified_email", True),
                    role=user_role,
                    oauth_provider="linkedin",
                    oauth_id=user_info.get("id"),
                    oauth_access_token=tokens.get("access_token"),
                    oauth_token_expires_at=datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 5184000)),
                    created_at=datetime.utcnow(),
                    last_login=datetime.utcnow()
                )
                await new_user.save()
                
                # Create role-specific profile
                try:
                    from backend.database.services import EmployerService, JobSeekerService
                    from backend.database.database import get_database
                    from backend.models.mongodb_models import GeekWorker, Freelancer
                    
                    db = await get_database()
                    
                    if user_role == UserRole.EMPLOYER:
                        # Create employer profile
                        employer_data = {
                            "company_name": f"{user_info.get('given_name', '')} {user_info.get('family_name', '')} Company",
                            "company_email": email,
                            "company_description": "New employer profile from LinkedIn OAuth",
                            "industry": "Not specified",
                            "company_size": "startup",
                            "location": "Not specified"
                        }
                        await EmployerService.create_employer(db, employer_data, str(new_user.id))
                        logger.info(f"Created employer profile for LinkedIn OAuth user: {email}")
                    elif user_role == UserRole.GEEK_WORKER:
                        # Create geek worker profile
                        geek_worker = GeekWorker(
                            user_id=new_user.id,
                            professional_title="Software Developer",
                            bio="New geek worker profile from LinkedIn OAuth",
                            skills=[],
                            specializations=[],
                            experience_level="entry",
                            years_of_experience=0,
                            hourly_rate=0.0,
                            availability="available",
                            remote_work_preference=True,
                            languages=["English"],
                            programming_languages=[],
                            frameworks=[],
                            timezone="UTC",
                            verified=False,
                            rating=0.0,
                            total_projects=0,
                            certifications=[],
                            education_level="bachelor",
                            field_of_study="Computer Science"
                        )
                        await geek_worker.save()
                        logger.info(f"Created geek worker profile for LinkedIn OAuth user: {email}")
                    elif user_role == UserRole.FREELANCER:
                        # Create freelancer profile
                        freelancer = Freelancer(
                            user_id=new_user.id,
                            professional_title="Freelancer",
                            bio="New freelancer profile from LinkedIn OAuth",
                            skills=[],
                            specializations=[],
                            experience_level="entry",
                            years_of_experience=0,
                            hourly_rate=0.0,
                            availability="available",
                            remote_work_preference=True,
                            languages=["English"],
                            timezone="UTC",
                            verified=False,
                            rating=0.0,
                            total_projects=0,
                            certifications=[],
                            education_level="bachelor",
                            field_of_study="Not specified"
                        )
                        await freelancer.save()
                        logger.info(f"Created freelancer profile for LinkedIn OAuth user: {email}")
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
                        logger.info(f"Created job seeker profile for LinkedIn OAuth user: {email}")
                        
                except Exception as profile_error:
                    logger.warning(f"Failed to create profile for LinkedIn OAuth user: {profile_error}")
                
                # Create lead for new OAuth user
                try:
                    lead_service = LeadService()
                    await lead_service.create_lead_from_signup(
                        email=email,
                        name=user_info.get("name", ""),
                        role=user_role,
                        source="linkedin_auth",
                        metadata={
                            "oauth_provider": "linkedin",
                            "oauth_id": user_info.get("id"),
                            "verified_email": user_info.get("verified_email", True),
                            "profile_picture": user_info.get("picture", "")
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to create lead for LinkedIn OAuth user {email}: {e}")
                
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
        """Validate OAuth access token with LinkedIn"""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.linkedin.com/v2/people/~",
                    headers=headers
                )
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"Error validating OAuth token: {e}")
            return False
    
    async def revoke_oauth_token(self, token: str) -> bool:
        """Revoke OAuth token (LinkedIn doesn't provide a revoke endpoint)"""
        # LinkedIn doesn't provide a token revocation endpoint
        # Tokens expire automatically after 60 days
        logger.info("LinkedIn OAuth tokens cannot be revoked programmatically")
        return True

# Global instance
linkedin_oauth_service = LinkedInOAuthService()