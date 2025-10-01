from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class EmailUserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class EmailMessageStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class EmailPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


# Email User Schemas
class EmailUserBase(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    personal_email: Optional[EmailStr] = None
    role: EmailUserRole = EmailUserRole.USER


class EmailUserCreate(EmailUserBase):
    send_welcome_email: bool = True
    
    @field_validator('personal_email')
    @classmethod
    def validate_personal_email(cls, v, info):
        if hasattr(info, 'data') and info.data.get('send_welcome_email', True) and not v:
            raise ValueError('Personal email is required when sending welcome email')
        return v


class EmailUserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    personal_email: Optional[EmailStr] = None
    role: Optional[EmailUserRole] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_locked: Optional[bool] = None


class EmailUserResponse(EmailUserBase):
    id: str
    is_active: bool
    is_verified: bool
    is_locked: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    password_reset_at: Optional[datetime] = None
    failed_login_attempts: int
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class EmailUsersListResponse(BaseModel):
    users: List[EmailUserResponse]
    total: int
    skip: int
    limit: int


class PasswordResetRequest(BaseModel):
    email: EmailStr


class EmailTestRequest(BaseModel):
    to_email: EmailStr
    subject: Optional[str] = None
    body: Optional[str] = None


class EmailSendRequest(BaseModel):
    to_emails: List[EmailStr]
    subject: str
    body: str
    cc_emails: Optional[List[EmailStr]] = None
    bcc_emails: Optional[List[EmailStr]] = None
    is_draft: bool = False


# Email Message Schemas
class EmailMessageBase(BaseModel):
    to: EmailStr
    subject: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    cc: Optional[str] = None
    bcc: Optional[str] = None
    html_content: Optional[str] = None
    priority: EmailPriority = EmailPriority.NORMAL


class EmailMessageCreate(EmailMessageBase):
    pass


class EmailMessageUpdate(BaseModel):
    subject: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    is_starred: Optional[bool] = None
    is_archived: Optional[bool] = None
    is_spam: Optional[bool] = None
    is_read: Optional[bool] = None


class EmailMessageResponse(BaseModel):
    id: str
    from_email: str = Field(alias="from")
    to_email: str = Field(alias="to")
    cc_email: Optional[str] = None
    bcc_email: Optional[str] = None
    subject: str
    content: str
    html_content: Optional[str] = None
    priority: EmailPriority
    status: EmailMessageStatus
    is_starred: bool
    is_archived: bool
    is_spam: bool
    is_draft: bool
    is_read: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class EmailMessagesListResponse(BaseModel):
    messages: List[EmailMessageResponse]
    total: int
    skip: int
    limit: int


# Email Template Schemas
class EmailTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    subject_template: str = Field(..., min_length=1, max_length=500)
    content_template: str = Field(..., min_length=1)
    html_template: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    is_active: bool = True


class EmailTemplateCreate(EmailTemplateBase):
    pass


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    subject_template: Optional[str] = Field(None, min_length=1, max_length=500)
    content_template: Optional[str] = Field(None, min_length=1)
    html_template: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class EmailTemplateResponse(EmailTemplateBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class EmailTemplatesListResponse(BaseModel):
    templates: List[EmailTemplateResponse]
    total: int
    skip: int
    limit: int


# Email Folder Schemas
class EmailFolderBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class EmailFolderCreate(EmailFolderBase):
    pass


class EmailFolderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class EmailFolderResponse(EmailFolderBase):
    id: str
    user_id: str
    is_system: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class EmailFoldersListResponse(BaseModel):
    folders: List[EmailFolderResponse]
    total: int


# Email Signature Schemas
class EmailSignatureBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)
    html_content: Optional[str] = None
    is_default: bool = False
    is_active: bool = True


class EmailSignatureCreate(EmailSignatureBase):
    pass


class EmailSignatureUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    content: Optional[str] = Field(None, min_length=1)
    html_content: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class EmailSignatureResponse(EmailSignatureBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class EmailSignaturesListResponse(BaseModel):
    signatures: List[EmailSignatureResponse]
    total: int


# Email Statistics Schemas
class EmailStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_messages: int
    messages_sent_today: int
    messages_sent_this_week: int
    messages_sent_this_month: int
    failed_messages: int
    spam_messages: int
    starred_messages: int
    archived_messages: int


# Bulk Operations Schemas
class BulkEmailUserAction(BaseModel):
    user_ids: List[str]
    action: str = Field(..., pattern=r'^(activate|deactivate|delete|reset_password)$')


class BulkEmailMessageAction(BaseModel):
    message_ids: List[str]
    action: str = Field(..., pattern=r'^(star|unstar|archive|unarchive|mark_spam|mark_not_spam|delete)$')


# Search Schemas
class EmailUserSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    filters: Optional[dict] = None
    sort_by: Optional[str] = Field(None, pattern=r'^(email|name|created_at|last_login)$')
    sort_order: Optional[str] = Field('asc', pattern=r'^(asc|desc)$')
    skip: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=100)


class EmailMessageSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    filters: Optional[dict] = None
    sort_by: Optional[str] = Field(None, pattern=r'^(subject|from_email|to_email|created_at|sent_at)$')
    sort_order: Optional[str] = Field('desc', pattern=r'^(asc|desc)$')
    skip: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=100)


# Email Compose Schemas
class EmailComposeRequest(BaseModel):
    to: List[EmailStr]
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None
    subject: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    html_content: Optional[str] = None
    priority: EmailPriority = EmailPriority.NORMAL
    save_as_draft: bool = False
    send_later: Optional[datetime] = None
    template_id: Optional[str] = None
    signature_id: Optional[str] = None
    attachments: Optional[List[str]] = None  # File paths or IDs


class EmailReplyRequest(BaseModel):
    message_id: str
    content: str = Field(..., min_length=1)
    html_content: Optional[str] = None
    reply_all: bool = False
    include_original: bool = True
    signature_id: Optional[str] = None
    attachments: Optional[List[str]] = None


class EmailForwardRequest(BaseModel):
    message_id: str
    to: List[EmailStr]
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None
    content: Optional[str] = None
    html_content: Optional[str] = None
    signature_id: Optional[str] = None
    attachments: Optional[List[str]] = None