# from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Table, Enum  # Using MongoDB instead
# from sqlalchemy.orm import relationship  # Using MongoDB instead
# from sqlalchemy.sql import func  # Using MongoDB instead
# from sqlalchemy.dialects.postgresql import UUID  # Using MongoDB instead
from datetime import datetime
import uuid
import enum
# from backend.database.models import Base
# TODO: Migrate email models to MongoDB or handle email functionality differently
# Note: This file contains SQLAlchemy models that need to be converted to MongoDB models


class EmailUserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class EmailMessageStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class EmailPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


# TODO: All SQLAlchemy models below need to be migrated to MongoDB
# The following models are commented out due to missing Base class from backend.database.models

# class EmailUser(Base):
#     """Email user model for organization email accounts"""
#     __tablename__ = "email_users"
#     
#     id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
#     email = Column(String(255), unique=True, index=True, nullable=False)
#     first_name = Column(String(100), nullable=False)
#     last_name = Column(String(100), nullable=False)
#     personal_email = Column(String(255), nullable=True)  # For password reset notifications
#     role = Column(Enum(EmailUserRole), default=EmailUserRole.USER, nullable=False)
#     password_hash = Column(String(255), nullable=False)
#     
#     # Status fields
#     is_active = Column(Boolean, default=True, nullable=False)
#     is_verified = Column(Boolean, default=False, nullable=False)
#     is_locked = Column(Boolean, default=False, nullable=False)
#     
#     # Timestamps
#     created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now())
#     last_login = Column(DateTime(timezone=True))
#     password_reset_at = Column(DateTime(timezone=True))
#     deleted_at = Column(DateTime(timezone=True))
#     
#     # Audit fields
#     created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
#     updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
#     password_reset_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
#     deleted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
#     
#     # Login attempt tracking
#     failed_login_attempts = Column(Integer, default=0)
#     last_failed_login = Column(DateTime(timezone=True))
#     
#     # Relationships
#     sent_messages = relationship("EmailMessage", foreign_keys="EmailMessage.from_user_id", back_populates="sender")
#     received_messages = relationship("EmailMessage", foreign_keys="EmailMessage.to_user_id", back_populates="recipient")
#     
#     def __repr__(self):
#         return f"<EmailUser(email='{self.email}', name='{self.first_name} {self.last_name}')>"


# class EmailMessage(Base):
#     """Email message model for tracking sent/received emails"""
#     __tablename__ = "email_messages"
#     
#     id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
#     
#     # Email addresses
#     from_email = Column(String(255), nullable=False, index=True)
#     to_email = Column(String(255), nullable=False, index=True)
#     cc_email = Column(Text)  # Comma-separated list
#     bcc_email = Column(Text)  # Comma-separated list
#     reply_to = Column(String(255))
#     
#     # Content
#     subject = Column(String(500), nullable=False)
#     content = Column(Text, nullable=False)
#     html_content = Column(Text)
#     
#     # Metadata
#     priority = Column(Enum(EmailPriority), default=EmailPriority.NORMAL)
#     status = Column(Enum(EmailMessageStatus), default=EmailMessageStatus.PENDING, nullable=False)
#     message_id = Column(String(255))  # Email Message-ID header
#     thread_id = Column(String(255))  # For email threading
#     
#     # Flags
#     is_starred = Column(Boolean, default=False)
#     is_archived = Column(Boolean, default=False)
#     is_spam = Column(Boolean, default=False)
#     is_draft = Column(Boolean, default=False)
#     is_read = Column(Boolean, default=False)
#     
#     # Timestamps
#     created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now())
#     sent_at = Column(DateTime(timezone=True))
#     delivered_at = Column(DateTime(timezone=True))
#     read_at = Column(DateTime(timezone=True))
#     
#     # Error handling
#     error_message = Column(Text)
#     retry_count = Column(Integer, default=0)
#     
#     # Foreign keys
#     from_user_id = Column(String(36), ForeignKey("email_users.id"))
#     to_user_id = Column(String(36), ForeignKey("email_users.id"))
#     
#     # Audit fields
#     created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
#     updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
#     
#     # Relationships
#     sender = relationship("EmailUser", foreign_keys=[from_user_id], back_populates="sent_messages")
#     recipient = relationship("EmailUser", foreign_keys=[to_user_id], back_populates="received_messages")
#     attachments = relationship("EmailAttachment", back_populates="message", cascade="all, delete-orphan")
#     
#     def __repr__(self):
#         return f"<EmailMessage(subject='{self.subject}', from='{self.from_email}', to='{self.to_email}')>"


# class EmailAttachment(Base):
#     """Email attachment model"""
#     __tablename__ = "email_attachments"
#     
#     id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
#     message_id = Column(String(36), ForeignKey("email_messages.id"), nullable=False)
#     
#     filename = Column(String(255), nullable=False)
#     content_type = Column(String(100))
#     file_size = Column(Integer)
#     file_path = Column(String(500))  # Path to stored file
#     
#     # Timestamps
#     created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
#     
#     # Relationships
#     message = relationship("EmailMessage", back_populates="attachments")
#     
#     def __repr__(self):
#         return f"<EmailAttachment(filename='{self.filename}', message_id='{self.message_id}')>"


# class EmailFolder(Base):
#     """Email folder model for organizing emails (like Gmail labels)"""
#     __tablename__ = "email_folders"
#     
#     id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
#     user_id = Column(String(36), ForeignKey("email_users.id"), nullable=False)
#     
#     name = Column(String(100), nullable=False)
#     color = Column(String(7))  # Hex color code
#     is_system = Column(Boolean, default=False)  # System folders like Inbox, Sent, etc.
#     
#     # Timestamps
#     created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now())
#     
#     def __repr__(self):
#         return f"<EmailFolder(name='{self.name}', user_id='{self.user_id}')>"


# class EmailMessageFolder(Base):
#     """Many-to-many relationship between messages and folders"""
#     __tablename__ = "email_message_folders"
#     
#     id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
#     message_id = Column(String(36), ForeignKey("email_messages.id"), nullable=False)
#     folder_id = Column(String(36), ForeignKey("email_folders.id"), nullable=False)
#     
#     # Timestamps
#     created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# class EmailSignature(Base):
#     """Email signature model for user signatures"""
#     __tablename__ = "email_signatures"
#     
#     id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
#     user_id = Column(String(36), ForeignKey("email_users.id"), nullable=False)
#     
#     name = Column(String(100), nullable=False)
#     content = Column(Text, nullable=False)
#     html_content = Column(Text)
#     
#     is_default = Column(Boolean, default=False)
#     is_active = Column(Boolean, default=True)
#     
#     # Timestamps
#     created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now())
#     
#     def __repr__(self):
#         return f"<EmailSignature(name='{self.name}', user_id='{self.user_id}')>"