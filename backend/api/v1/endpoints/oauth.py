from fastapi import APIRouter, HTTPException, Query, Depends, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
import logging
from backend.services.oauth_service import oauth_service
from backend.services.linkedin_oauth_service import linkedin_oauth_service
from backend.core.config import settings
from backend.models.mongodb_models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["OAuth Authentication"])

# Response models
class OAuthURLResponse(BaseModel):
    auth_url: str
    state: str

class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict

class OAuthErrorResponse(BaseModel):
    error: str
    error_description: Optional[str] = None

@router.get("/google/login", response_model=OAuthURLResponse)
async def google_oauth_login(
    redirect_url: Optional[str] = Query(None, description="URL to redirect after successful authentication"),
    role: Optional[str] = Query(None, description="User role for registration (employer or job_seeker)")
):
    """Initiate Google OAuth login flow"""
    try:
        # Generate state parameter for security
        import secrets
        state = secrets.token_urlsafe(32)
        
        # Store redirect URL in state if provided (in production, use Redis or database)
        if redirect_url:
            # For now, we'll include it in the state (in production, store separately)
            state = f"{state}|{redirect_url}"
        
        auth_url = oauth_service.generate_auth_url(state=state, role=role)
        
        return OAuthURLResponse(
            auth_url=auth_url,
            state=state
        )
        
    except Exception as e:
        logger.error(f"Error generating OAuth URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate OAuth URL"
        )

@router.get("/google/callback")
async def google_oauth_callback(
    code: Optional[str] = Query(None, description="Authorization code from Google"),
    state: Optional[str] = Query(None, description="State parameter for security"),
    error: Optional[str] = Query(None, description="Error from OAuth provider")
):
    """Handle Google OAuth callback"""
    try:
        # Check for OAuth errors
        if error:
            logger.error(f"OAuth error: {error}")
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/auth/error?error={error}",
                status_code=status.HTTP_302_FOUND
            )
        
        # Validate required parameters
        if not code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authorization code is required"
            )
        
        # Exchange code for tokens
        tokens = await oauth_service.exchange_code_for_tokens(code)
        
        # Get user information
        user_info = await oauth_service.get_user_info(tokens["access_token"])
        
        # Extract role and redirect URL from state if present
        role = None
        redirect_url = settings.FRONTEND_URL
        if state:
            # Parse state for role and redirect URL
            # Format: "token|role:ROLE_NAME" or "token|redirect_url" or "token|redirect_url|role:ROLE_NAME"
            parts = state.split("|")
            for part in parts[1:]:  # Skip the first part (token)
                if part.startswith("role:"):
                    role = part.split(":", 1)[1]
                elif not part.startswith("role:"):
                    redirect_url = part
        
        # Authenticate or create user
        user = await oauth_service.authenticate_or_create_user(user_info, tokens, role=role)
        
        # Generate JWT token
        jwt_token = oauth_service.generate_jwt_token(user)
        
        # Redirect to frontend with token
        return RedirectResponse(
            url=f"{redirect_url}/auth/success?token={jwt_token}",
            status_code=status.HTTP_302_FOUND
        )
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/error?error=oauth_failed",
            status_code=status.HTTP_302_FOUND
        )

@router.post("/google/token", response_model=OAuthTokenResponse)
async def google_oauth_token(
    code: str,
    state: Optional[str] = None,
    role: Optional[str] = None
):
    """Exchange authorization code for JWT token (API endpoint)"""
    try:
        # Exchange code for tokens
        tokens = await oauth_service.exchange_code_for_tokens(code)
        
        # Get user information
        user_info = await oauth_service.get_user_info(tokens["access_token"])
        
        # Extract role from state if not provided directly
        if not role and state:
            parts = state.split("|")
            for part in parts:
                if part.startswith("role:"):
                    role = part.split(":", 1)[1]
                    break
        
        # Authenticate or create user
        user = await oauth_service.authenticate_or_create_user(user_info, tokens, role=role)
        
        # Generate JWT token
        jwt_token = oauth_service.generate_jwt_token(user)
        
        return OAuthTokenResponse(
            access_token=jwt_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "id": str(user.id),
                "email": user.email,
                "name": user.display_name,
                "role": user.role.value,
                "is_verified": user.is_verified,
                "profile_picture": user.profile_picture
            }
        )
        
    except Exception as e:
        logger.error(f"Token exchange error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange code for token: {str(e)}"
        )

@router.post("/refresh")
async def refresh_oauth_token(
    refresh_token: str
):
    """Refresh OAuth access token"""
    try:
        tokens = await oauth_service.refresh_access_token(refresh_token)
        
        return {
            "access_token": tokens["access_token"],
            "expires_in": tokens.get("expires_in", 3600),
            "token_type": "bearer"
        }
        
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to refresh token"
        )

@router.post("/revoke")
async def revoke_oauth_token(
    token: str
):
    """Revoke OAuth token"""
    try:
        success = await oauth_service.revoke_oauth_token(token)
        
        if success:
            return {"message": "Token revoked successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to revoke token"
            )
            
    except Exception as e:
        logger.error(f"Token revocation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke token"
        )

# LinkedIn OAuth endpoints
@router.get("/linkedin/login", response_model=OAuthURLResponse)
async def linkedin_oauth_login(
    redirect_url: Optional[str] = Query(None, description="URL to redirect after successful authentication"),
    role: Optional[str] = Query(None, description="User role for registration (employer, job_seeker, geek_worker, or freelancer)")
):
    """Initiate LinkedIn OAuth login flow"""
    try:
        # Generate state parameter for security
        import secrets
        state = secrets.token_urlsafe(32)
        
        # Store redirect URL in state if provided
        if redirect_url:
            state = f"{state}|{redirect_url}"
        
        auth_url = linkedin_oauth_service.generate_auth_url(state=state, role=role)
        
        return OAuthURLResponse(
            auth_url=auth_url,
            state=state
        )
        
    except Exception as e:
        logger.error(f"Error generating LinkedIn OAuth URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate LinkedIn OAuth URL"
        )

@router.get("/linkedin/callback")
async def linkedin_oauth_callback(
    code: Optional[str] = Query(None, description="Authorization code from LinkedIn"),
    state: Optional[str] = Query(None, description="State parameter for security"),
    error: Optional[str] = Query(None, description="Error from OAuth provider")
):
    """Handle LinkedIn OAuth callback"""
    try:
        # Check for OAuth errors
        if error:
            logger.error(f"LinkedIn OAuth error: {error}")
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/auth/error?error={error}",
                status_code=status.HTTP_302_FOUND
            )
        
        # Validate required parameters
        if not code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authorization code is required"
            )
        
        # Exchange code for tokens
        tokens = await linkedin_oauth_service.exchange_code_for_tokens(code)
        
        # Get user information
        user_info = await linkedin_oauth_service.get_user_info(tokens["access_token"])
        
        # Extract role and redirect URL from state if present
        role = None
        redirect_url = settings.FRONTEND_URL
        if state:
            parts = state.split("|")
            for part in parts[1:]:  # Skip the first part (token)
                if part.startswith("role:"):
                    role = part.split(":", 1)[1]
                elif not part.startswith("role:"):
                    redirect_url = part
        
        # Authenticate or create user
        user = await linkedin_oauth_service.authenticate_or_create_user(user_info, tokens, role=role)
        
        # Generate JWT token
        jwt_token = linkedin_oauth_service.generate_jwt_token(user)
        
        # Redirect to frontend with token
        return RedirectResponse(
            url=f"{redirect_url}/auth/success?token={jwt_token}",
            status_code=status.HTTP_302_FOUND
        )
        
    except Exception as e:
        logger.error(f"LinkedIn OAuth callback error: {e}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/error?error=linkedin_oauth_failed",
            status_code=status.HTTP_302_FOUND
        )

@router.post("/linkedin/token", response_model=OAuthTokenResponse)
async def linkedin_oauth_token(
    code: str,
    state: Optional[str] = None,
    role: Optional[str] = None
):
    """Exchange LinkedIn authorization code for JWT token (API endpoint)"""
    try:
        # Exchange code for tokens
        tokens = await linkedin_oauth_service.exchange_code_for_tokens(code)
        
        # Get user information
        user_info = await linkedin_oauth_service.get_user_info(tokens["access_token"])
        
        # Extract role from state if not provided directly
        if not role and state:
            parts = state.split("|")
            for part in parts:
                if part.startswith("role:"):
                    role = part.split(":", 1)[1]
                    break
        
        # Authenticate or create user
        user = await linkedin_oauth_service.authenticate_or_create_user(user_info, tokens, role=role)
        
        # Generate JWT token
        jwt_token = linkedin_oauth_service.generate_jwt_token(user)
        
        return OAuthTokenResponse(
            access_token=jwt_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "id": str(user.id),
                "email": user.email,
                "name": user.display_name,
                "role": user.role.value,
                "is_verified": user.is_verified,
                "profile_picture": user.profile_picture
            }
        )
        
    except Exception as e:
        logger.error(f"LinkedIn token exchange error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange LinkedIn code for token: {str(e)}"
        )

@router.get("/status")
async def oauth_status():
    """Get OAuth configuration status"""
    return {
        "google_oauth_enabled": settings.GOOGLE_OAUTH_ENABLED,
        "google_client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "google_redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "google_scopes": settings.GOOGLE_OAUTH_SCOPES,
        "linkedin_oauth_enabled": settings.LINKEDIN_OAUTH_ENABLED,
        "linkedin_client_id": settings.LINKEDIN_OAUTH_CLIENT_ID,
        "linkedin_redirect_uri": settings.LINKEDIN_OAUTH_REDIRECT_URI,
        "linkedin_scopes": settings.LINKEDIN_OAUTH_SCOPES
    }