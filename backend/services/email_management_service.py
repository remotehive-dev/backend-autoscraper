from motor.motor_asyncio import AsyncIOMotorDatabase
# from bson import ObjectId  # Removed to fix Pydantic schema generation
from typing import List, Optional, Dict, Any
# MongoDB models are handled as dictionaries
from backend.services.email_service import EmailService
from backend.core.security import get_password_hash
import uuid
from datetime import datetime
import secrets
import string
import logging

logger = logging.getLogger(__name__)

class EmailManagementService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.email_service = EmailService(db)
    
    async def create_email_user(
        self,
        email_address: str,
        full_name: str,
        personal_email: str,
        created_by: str,
        role: str = 'user'
    ) -> Dict[str, Any]:
        """Create new email user and send welcome email"""
        try:
            # Generate temporary password
            temp_password = self._generate_temp_password()
            
            # Create email user document
            email_user = {
                "_id": str(uuid.uuid4()),
                "email_address": email_address,
                "full_name": full_name,
                "personal_email": personal_email,
                "password_hash": get_password_hash(temp_password),
                "role": role,
                "is_active": True,
                "created_by": created_by,
                "created_at": datetime.utcnow()
            }
            
            await self.db.email_users.insert_one(email_user)
            
            # Create default folders
            await self._create_default_folders(str(email_user["_id"]))
            
            # Create default signature
            await self._create_default_signature(str(email_user["_id"]), full_name)
            
            # Send welcome email to personal email
            await self.email_service.send_welcome_email(
                to_email=personal_email,
                user_name=full_name,
                temp_password=temp_password
            )
            
            logger.info(f"Email user created: {email_address}")
            
            return {
                'success': True,
                'user_id': str(email_user["_id"]),
                'email_address': email_address,
                'temp_password': temp_password,
                'message': 'Email user created successfully. Welcome email sent to personal email.'
            }
            
        except Exception as e:
            logger.error(f"Failed to create email user: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def delete_email_user(self, user_id: str, deleted_by: str) -> Dict[str, Any]:
        """Soft delete email user"""
        try:
            email_user = await self.db.email_users.find_one({
                "_id": user_id,
                "is_active": True
            })
            
            if not email_user:
                return {
                    'success': False,
                    'error': 'Email user not found'
                }
            
            # Soft delete
            await self.db.email_users.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "deleted_by": deleted_by,
                        "deleted_at": datetime.utcnow(),
                        "is_active": False
                    }
                }
            )
            
            logger.info(f"Email user deleted: {email_user.get('email_address')}")
            
            return {
                'success': True,
                'message': 'Email user deleted successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to delete email user: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def reset_user_password(self, user_id: str, reset_by: str) -> Dict[str, Any]:
        """Reset user password and send notification"""
        try:
            email_user = await self.db.email_users.find_one({
                "_id": user_id,
                "is_active": True
            })
            
            if not email_user:
                return {
                    'success': False,
                    'error': 'Email user not found'
                }
            
            # Generate new temporary password
            new_temp_password = self._generate_temp_password()
            
            # Update password
            await self.db.email_users.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "password_hash": get_password_hash(new_temp_password),
                        "password_reset_by": reset_by,
                        "password_reset_at": datetime.utcnow(),
                        "must_change_password": True
                    }
                }
            )
            
            # Send password reset email to personal email
            await self.email_service.send_notification_email(
                to_email=email_user.get("personal_email"),
                title='Password Reset - RemoteHive Email',
                message=f'Your email password has been reset by an administrator. Your new temporary password is: {new_temp_password}. Please log in and change your password immediately.'
            )
            
            logger.info(f"Password reset for user: {email_user.get('email_address')}")
            
            return {
                'success': True,
                'temp_password': new_temp_password,
                'message': 'Password reset successfully. Notification sent to personal email.'
            }
            
        except Exception as e:
            logger.error(f"Failed to reset password: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def search_email_users(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search email users by name or email"""
        cursor = self.db.email_users.find({
            "is_active": True,
            "$or": [
                {"full_name": {"$regex": query, "$options": "i"}},
                {"email_address": {"$regex": query, "$options": "i"}}
            ]
        }).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def get_all_email_users(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all active email users"""
        cursor = self.db.email_users.find({
            "is_active": True
        }).skip(offset).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def send_email(
        self,
        from_user_id: str,
        to_emails: List[str],
        subject: str,
        body: str,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
        is_draft: bool = False
    ) -> Dict[str, Any]:
        """Send email from user"""
        try:
            from_user = await self.db.email_users.find_one({
                "_id": from_user_id,
                "is_active": True
            })
            
            if not from_user:
                return {
                    'success': False,
                    'error': 'Sender not found'
                }
            
            # Create email message record
            message_id = ObjectId()
            email_message = {
                "_id": message_id,
                "from_user_id": from_user_id,
                "subject": subject,
                "body": body,
                "is_draft": is_draft,
                "sent_at": None if is_draft else datetime.utcnow(),
                "created_at": datetime.utcnow()
            }
            
            await self.db.email_messages.insert_one(email_message)
            
            if not is_draft:
                # Send to all recipients
                all_recipients = to_emails + (cc_emails or []) + (bcc_emails or [])
                
                for recipient in all_recipients:
                    success = await self.email_service.send_email(
                        to_email=recipient,
                        subject=subject,
                        body=body,
                        from_email=from_user.get("email_address"),
                        attachments=attachments
                    )
                    
                    if not success:
                        logger.warning(f"Failed to send email to {recipient}")
                
                # Move to sent folder
                await self._add_message_to_folder(str(message_id), from_user_id, 'sent')
            else:
                # Move to drafts folder
                await self._add_message_to_folder(str(message_id), from_user_id, 'drafts')
            
            return {
                'success': True,
                'message_id': str(message_id),
                'message': 'Email sent successfully' if not is_draft else 'Draft saved successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_user_messages(
        self,
        user_id: str,
        folder_name: str = 'inbox',
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get user messages from specific folder"""
        folder = await self.db.email_folders.find_one({
            "user_id": user_id,
            "name": folder_name
        })
        
        if not folder:
            return []
        
        # Get message IDs from folder
        message_folders = await self.db.email_message_folders.find({
            "folder_id": folder["_id"]
        }).skip(offset).limit(limit).to_list(length=limit)
        
        if not message_folders:
            return []
        
        message_ids = [mf["message_id"] for mf in message_folders]
        
        # Get messages
        messages = await self.db.email_messages.find({
            "_id": {"$in": message_ids}
        }).sort("created_at", -1).to_list(length=limit)
        
        return messages
    
    async def star_message(self, user_id: str, message_id: str) -> Dict[str, Any]:
        """Star/unstar a message"""
        try:
            # Add to starred folder
            result = await self._add_message_to_folder(message_id, user_id, 'starred')
            
            if result['success']:
                return {
                    'success': True,
                    'message': 'Message starred successfully'
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to star message: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def move_to_spam(self, user_id: str, message_id: str) -> Dict[str, Any]:
        """Move message to spam folder"""
        try:
            result = await self._add_message_to_folder(message_id, user_id, 'spam')
            
            if result['success']:
                return {
                    'success': True,
                    'message': 'Message moved to spam'
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to move message to spam: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_temp_password(self, length: int = 12) -> str:
        """Generate temporary password"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    async def _create_default_folders(self, user_id: str):
        """Create default email folders for user"""
        default_folders = ['inbox', 'sent', 'drafts', 'spam', 'trash', 'starred']
        
        folders_to_insert = []
        for folder_name in default_folders:
            folder = {
                "_id": ObjectId(),
                "user_id": user_id,
                "name": folder_name,
                "display_name": folder_name.title(),
                "is_system": True,
                "created_at": datetime.utcnow()
            }
            folders_to_insert.append(folder)
        
        await self.db.email_folders.insert_many(folders_to_insert)
    
    async def _create_default_signature(self, user_id: str, full_name: str):
        """Create default email signature"""
        signature = {
            "_id": ObjectId(),
            "user_id": user_id,
            "name": 'Default',
            "content": f'<p>Best regards,<br>{full_name}<br>RemoteHive Team</p>',
            "is_default": True,
            "created_at": datetime.utcnow()
        }
        await self.db.email_signatures.insert_one(signature)
    
    async def _add_message_to_folder(
        self,
        message_id: str,
        user_id: str,
        folder_name: str
    ) -> Dict[str, Any]:
        """Add message to specific folder"""
        try:
            folder = await self.db.email_folders.find_one({
                "user_id": user_id,
                "name": folder_name
            })
            
            if not folder:
                return {
                    'success': False,
                    'error': f'Folder {folder_name} not found'
                }
            
            # Check if already exists
            existing = await self.db.email_message_folders.find_one({
                "message_id": message_id,
                "folder_id": folder["_id"]
            })
            
            if not existing:
                message_folder = {
                    "_id": ObjectId(),
                    "message_id": message_id,
                    "folder_id": folder["_id"],
                    "added_at": datetime.utcnow()
                }
                await self.db.email_message_folders.insert_one(message_folder)
            
            return {
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Failed to add message to folder: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }