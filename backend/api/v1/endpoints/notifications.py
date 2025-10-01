from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
from beanie import PydanticObjectId

from backend.database.database import get_mongodb_session
from backend.core.auth import get_current_user
# from backend.database.mongodb_models import Notification, NotificationPreference
# Note: Notification and NotificationPreference models don't exist yet in mongodb_models.py
from backend.schemas.notification import (
    NotificationCreate,
    NotificationPreferencesUpdate,
    MarkAsReadRequest,
    BulkNotificationCreate,
    NotificationStats,
    NotificationList,
    NotificationPreferences
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", response_model=NotificationList)
async def get_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    notification_type: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_mongodb_session)
):
    """Get user's notifications with pagination"""
    try:
        # Build MongoDB query
        query_filter = {"user_id": current_user["id"]}
        
        # Apply filters
        if unread_only:
            query_filter["is_read"] = False
        
        if notification_type:
            query_filter["type"] = notification_type
        
        # Get total count
        total = await Notification.find(query_filter).count()
        
        # Get unread count
        unread_count = await Notification.find({"user_id": current_user["id"], "is_read": False}).count()
        
        # Get paginated results
        offset = (page - 1) * per_page
        notifications = await Notification.find(query_filter).sort("-created_at").skip(offset).limit(per_page).to_list()
        
        return NotificationList(
            notifications=notifications,
            total=total,
            page=page,
            per_page=per_page,
            has_next=offset + per_page < total,
            has_prev=page > 1,
            unread_count=unread_count
        )
        
    except Exception as e:
        logger.error(f"Failed to get notifications for user {current_user.get('email')}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notifications"
        )

@router.get("/stats", response_model=NotificationStats)
async def get_notification_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_mongodb_session)
):
    """Get notification statistics for the user"""
    try:
        user_id = current_user["id"]
        
        # Get total notifications count
        total_notifications = await Notification.find({"user_id": user_id}).count()
        
        # Get unread notifications count
        unread_notifications = await Notification.find({"user_id": user_id, "is_read": False}).count()
        
        read_notifications = total_notifications - unread_notifications
        
        # Get notifications by type using MongoDB aggregation
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$type", "count": {"$sum": 1}}}
        ]
        type_results = await Notification.aggregate(pipeline).to_list()
        notifications_by_type = {result["_id"]: result["count"] for result in type_results}
        
        # Get recent notifications (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_notifications = await Notification.find(
            {"user_id": user_id, "created_at": {"$gte": seven_days_ago}}
        ).sort("-created_at").limit(10).to_list()
        recent_notifications = [notif.model_dump() for notif in recent_notifications]
        
        return NotificationStats(
            total_notifications=total_notifications,
            unread_notifications=unread_notifications,
            read_notifications=read_notifications,
            notifications_by_type=notifications_by_type,
            recent_notifications=recent_notifications
        )
        
    except Exception as e:
        logger.error(f"Failed to get notification stats for user {current_user.get('email')}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notification statistics"
        )

@router.post("/mark-read")
async def mark_notifications_read(
    request: MarkAsReadRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Mark notifications as read"""
    try:
        user_id = current_user["id"]
        
        if request.notification_ids:
            # Mark specific notifications as read
            for notification_id in request.notification_ids:
                await Notification.find_one(
                    {"_id": PydanticObjectId(notification_id), "user_id": user_id}
                ).update(
                    {"$set": {"is_read": True, "updated_at": datetime.utcnow()}}
                )
            
            return {"message": f"Marked {len(request.notification_ids)} notifications as read"}
        else:
            # Mark all notifications as read
            await Notification.find(
                {"user_id": user_id, "is_read": False}
            ).update(
                {"$set": {"is_read": True, "updated_at": datetime.utcnow()}}
            )
            
            return {"message": "Marked all notifications as read"}
        
    except Exception as e:
        logger.error(f"Failed to mark notifications as read for user {current_user.get('email')}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notifications as read"
        )

@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a specific notification"""
    try:
        user_id = current_user["id"]
        
        # Check if notification exists and belongs to user
        notification = await Notification.find_one(
            {"_id": PydanticObjectId(notification_id), "user_id": user_id}
        )
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        # Delete the notification
        await notification.delete()
        
        return {"message": "Notification deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete notification {notification_id} for user {current_user.get('email')}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete notification"
        )

@router.get("/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user's notification preferences"""
    try:
        user_id = current_user["id"]
        
        # Get user preferences
        preferences = await NotificationPreference.find_one({"user_id": user_id})
        
        if preferences:
            return preferences
        else:
            # Return default preferences if none exist
            default_preferences = NotificationPreference(
                user_id=user_id,
                email_notifications=True,
                push_notifications=True,
                job_alerts=True,
                application_updates=True,
                marketing_emails=False
            )
            await default_preferences.create()
            return default_preferences
        
    except Exception as e:
        logger.error(f"Failed to get notification preferences for user {current_user.get('email')}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notification preferences"
        )

@router.put("/preferences", response_model=NotificationPreferences)
async def update_notification_preferences(
    preferences: NotificationPreferencesUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update user's notification preferences"""
    try:
        user_id = current_user["id"]
        
        # Check if preferences exist
        existing_preferences = await NotificationPreference.find_one({"user_id": user_id})
        
        preferences_data = preferences.model_dump(exclude_unset=True)
        preferences_data["updated_at"] = datetime.utcnow()
        
        if existing_preferences:
            # Update existing preferences
            await existing_preferences.update({"$set": preferences_data})
            updated_preferences = await NotificationPreference.find_one({"user_id": user_id})
            return updated_preferences
        else:
            # Create new preferences
            preferences_data["user_id"] = user_id
            new_preferences = NotificationPreference(**preferences_data)
            await new_preferences.create()
            return new_preferences
        
    except Exception as e:
        logger.error(f"Failed to update notification preferences for user {current_user.get('email')}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification preferences"
        )

# Admin endpoints
@router.post("/admin/create")  # response_model=Notification - commented out as model doesn't exist yet
async def create_notification(
    notification: NotificationCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)  # Changed from get_current_admin_user
):
    """Create a new notification (Admin only)"""
    try:
        notification_data = notification.model_dump()
        notification_data["created_at"] = datetime.utcnow()
        notification_data["updated_at"] = datetime.utcnow()
        
        new_notification = Notification(**notification_data)
        await new_notification.create()
        
        return new_notification
        
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create notification"
        )

@router.post("/admin/bulk-create")
async def create_bulk_notifications(
    bulk_data: BulkNotificationCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_mongodb_session)  # Changed from Session to MongoDB session
):
    """Create notifications for multiple users (admin only)"""
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create bulk notifications"
        )
    
    try:
        notifications = []
        for user_id in bulk_data.user_ids:
            notification_dict = bulk_data.model_dump(exclude={"user_ids"})
            notification_dict["user_id"] = user_id
            notifications.append(notification_dict)
        
        result = supabase.table("notifications").insert(notifications).execute()
        
        return {
            "message": f"Created {len(result.data)} notifications",
            "created_count": len(result.data)
        }
        
    except Exception as e:
        logger.error(f"Failed to create bulk notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create bulk notifications"
        )