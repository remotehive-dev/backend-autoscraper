from typing import Dict, Any, Optional
import httpx
from fastapi import HTTPException, status
from loguru import logger
import os
from datetime import datetime, timedelta
import jwt

class ClerkAuth:
    """Clerk Authentication Service for RemoteHive"""
    
    def __init__(self):
        self.clerk_secret_key = os.getenv("CLERK_SECRET_KEY")
        self.clerk_publishable_key = os.getenv("CLERK_PUBLISHABLE_KEY")
        self.clerk_api_url = "https://api.clerk.com/v1"
        
        if not self.clerk_secret_key:
            logger.warning("CLERK_SECRET_KEY not found in environment variables")
    
    async def verify_session_token(self, session_token: str) -> Dict[str, Any]:
        """Verify Clerk session token and return user data"""
        if not self.clerk_secret_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Clerk authentication not configured"
            )
        
        headers = {
            "Authorization": f"Bearer {self.clerk_secret_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.clerk_api_url}/sessions/{session_token}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    session_data = response.json()
                    
                    # Get user data
                    user_response = await client.get(
                        f"{self.clerk_api_url}/users/{session_data['user_id']}",
                        headers=headers
                    )
                    
                    if user_response.status_code == 200:
                        user_data = user_response.json()
                        return {
                            "user_id": user_data["id"],
                            "email": user_data["email_addresses"][0]["email_address"] if user_data["email_addresses"] else None,
                            "first_name": user_data["first_name"],
                            "last_name": user_data["last_name"],
                            "phone": user_data["phone_numbers"][0]["phone_number"] if user_data["phone_numbers"] else None,
                            "is_verified": user_data["email_addresses"][0]["verification"]["status"] == "verified" if user_data["email_addresses"] else False,
                            "created_at": user_data["created_at"],
                            "updated_at": user_data["updated_at"],
                            "metadata": user_data.get("public_metadata", {})
                        }
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid session token"
                        )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid session token"
                    )
                    
        except httpx.RequestError as e:
            logger.error(f"Error verifying Clerk session: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service unavailable"
            )
    
    async def create_user(self, email: str, password: str, first_name: str, last_name: str, 
                         phone: Optional[str] = None, role: str = "job_seeker") -> Dict[str, Any]:
        """Create a new user in Clerk"""
        if not self.clerk_secret_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Clerk authentication not configured"
            )
        
        headers = {
            "Authorization": f"Bearer {self.clerk_secret_key}",
            "Content-Type": "application/json"
        }
        
        user_data = {
            "email_address": [email],
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
            "public_metadata": {
                "role": role,
                "platform": "remotehive"
            }
        }
        
        if phone:
            user_data["phone_number"] = [phone]
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.clerk_api_url}/users",
                    headers=headers,
                    json=user_data
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"Clerk user created successfully: {response.status_code}")
                    return response.json()
                else:
                    try:
                        error_data = response.json()
                        error_message = "User creation failed"
                        if "errors" in error_data and error_data["errors"]:
                            error_message = error_data["errors"][0].get("message", error_message)
                        elif "message" in error_data:
                            error_message = error_data["message"]
                        
                        logger.error(f"Clerk user creation failed: {error_message}, Status: {response.status_code}, Response: {error_data}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=error_message
                        )
                    except ValueError as json_error:
                        logger.error(f"Clerk API error - Status: {response.status_code}, Response: {response.text}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"User creation failed: {response.text}"
                        )
                    
        except httpx.RequestError as e:
            logger.error(f"Error creating Clerk user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service unavailable"
            )
    
    async def update_user_metadata(self, user_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Update user metadata in Clerk"""
        if not self.clerk_secret_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Clerk authentication not configured"
            )
        
        headers = {
            "Authorization": f"Bearer {self.clerk_secret_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.clerk_api_url}/users/{user_id}",
                    headers=headers,
                    json={"public_metadata": metadata}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to update user metadata"
                    )
                    
        except httpx.RequestError as e:
            logger.error(f"Error updating Clerk user metadata: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service unavailable"
            )
    
    def get_frontend_config(self) -> Dict[str, str]:
        """Get Clerk configuration for frontend"""
        return {
            "publishable_key": self.clerk_publishable_key or "",
            "sign_in_url": "/sign-in",
            "sign_up_url": "/sign-up",
            "after_sign_in_url": "/dashboard",
            "after_sign_up_url": "/onboarding"
        }

# Global instance
clerk_auth = ClerkAuth()