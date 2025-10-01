from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime
from backend.core.enums import UserRole

# Base User Schema
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None

# User Creation Schema
class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.JOB_SEEKER
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

# User Update Schema
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    avatar_url: Optional[str] = None

# User Password Update Schema
class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

# User Response Schema
class User(UserBase):
    id: int
    role: UserRole
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# User in Database Schema (includes hashed password)
class UserInDB(User):
    hashed_password: str

# User Login Schema
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User

class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None

# User List Response
class UserList(BaseModel):
    users: List[User]
    total: int
    page: int
    per_page: int
    pages: int

# User Statistics Schema
class UserStats(BaseModel):
    total_users: int
    active_users: int
    verified_users: int
    super_admins: int
    admins: int
    employers: int
    job_seekers: int
    new_users_this_month: int