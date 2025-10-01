from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from typing import Optional
import logging

from backend.services.websocket_service import websocket_manager, CSVImportWebSocketHandler
from backend.services.csv_progress_tracker import CSVProgressTracker
from backend.core.auth import get_current_user
from backend.database.database import get_db_session
# TODO: MongoDB Migration - Update User import to use MongoDB models
# from backend.database.models import User
from backend.models.mongodb_models import User
# from sqlalchemy.orm import Session  # Using MongoDB instead

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

# Initialize handlers
csv_handler = None

def get_csv_handler(db = Depends(get_db_session)):
    global csv_handler
    if csv_handler is None:
        progress_tracker = CSVProgressTracker(db)
        csv_handler = CSVImportWebSocketHandler(progress_tracker)
    return csv_handler

@router.websocket("/csv-import/{upload_id}")
async def websocket_csv_import(
    websocket: WebSocket,
    upload_id: str,
    token: Optional[str] = None
):
    """
    WebSocket endpoint for CSV import progress tracking.
    
    Args:
        websocket: WebSocket connection
        upload_id: Upload identifier to track
        token: Authentication token (passed as query parameter)
    """
    try:
        # For WebSocket, we need to handle auth differently
        # Token should be passed as query parameter
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
            return
        
        # Validate token and get user
        # Note: In a real implementation, you'd validate the JWT token here
        # For now, we'll assume the token is valid and extract user_id
        user_id = "admin"  # This should be extracted from the validated token
        
        # Get database session
        db = next(get_db_session())
        progress_tracker = CSVProgressTracker(db)
        handler = CSVImportWebSocketHandler(progress_tracker)
        
        # Handle the connection
        await handler.handle_connection(
            websocket=websocket,
            upload_id=upload_id,
            user_id=user_id
        )
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for CSV import {upload_id}")
    except Exception as e:
        logger.error(f"WebSocket error for CSV import {upload_id}: {str(e)}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
        except:
            pass

@router.websocket("/admin/dashboard")
async def websocket_admin_dashboard(
    websocket: WebSocket,
    token: Optional[str] = None
):
    """
    WebSocket endpoint for admin dashboard real-time updates.
    
    Args:
        websocket: WebSocket connection
        token: Authentication token (passed as query parameter)
    """
    try:
        # Validate authentication
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
            return
        
        # Extract user_id from token (simplified for demo)
        user_id = "admin"
        
        # Connect to general admin notifications
        await websocket_manager.connect(
            websocket=websocket,
            connection_type='admin_general',
            identifier=None,
            user_id=user_id
        )
        
        # Send initial connection data
        stats = await websocket_manager.get_connection_stats()
        await websocket_manager.send_to_connection(websocket, {
            'type': 'dashboard_init',
            'connection_stats': stats
        })
        
        # Keep connection alive and handle messages
        while True:
            try:
                message = await websocket.receive_text()
                # Handle dashboard-specific messages here
                logger.info(f"Received dashboard message: {message}")
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling dashboard WebSocket message: {str(e)}")
                break
    
    except WebSocketDisconnect:
        logger.info("Admin dashboard WebSocket disconnected")
    except Exception as e:
        logger.error(f"Admin dashboard WebSocket error: {str(e)}")
    finally:
        await websocket_manager.disconnect(websocket)

@router.websocket("/scraper/{scraper_id}")
async def websocket_scraper_status(
    websocket: WebSocket,
    scraper_id: str,
    token: Optional[str] = None
):
    """
    WebSocket endpoint for scraper status tracking.
    
    Args:
        websocket: WebSocket connection
        scraper_id: Scraper identifier to track
        token: Authentication token (passed as query parameter)
    """
    try:
        # Validate authentication
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
            return
        
        user_id = "admin"
        
        # Connect to scraper status updates
        await websocket_manager.connect(
            websocket=websocket,
            connection_type='scraper_status',
            identifier=scraper_id,
            user_id=user_id
        )
        
        # Keep connection alive and handle messages
        while True:
            try:
                message = await websocket.receive_text()
                # Handle scraper-specific messages here
                logger.info(f"Received scraper message for {scraper_id}: {message}")
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling scraper WebSocket message: {str(e)}")
                break
    
    except WebSocketDisconnect:
        logger.info(f"Scraper WebSocket disconnected for {scraper_id}")
    except Exception as e:
        logger.error(f"Scraper WebSocket error for {scraper_id}: {str(e)}")
    finally:
        await websocket_manager.disconnect(websocket)

@router.websocket("/analytics/{dashboard_id}")
async def websocket_analytics(
    websocket: WebSocket,
    dashboard_id: str,
    token: Optional[str] = None
):
    """
    WebSocket endpoint for analytics dashboard real-time updates.
    
    Args:
        websocket: WebSocket connection
        dashboard_id: Dashboard identifier
        token: Authentication token (passed as query parameter)
    """
    try:
        # Validate authentication
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
            return
        
        user_id = "admin"
        
        # Connect to analytics updates
        await websocket_manager.connect(
            websocket=websocket,
            connection_type='analytics',
            identifier=dashboard_id,
            user_id=user_id
        )
        
        # Keep connection alive and handle messages
        while True:
            try:
                message = await websocket.receive_text()
                # Handle analytics-specific messages here
                logger.info(f"Received analytics message for {dashboard_id}: {message}")
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling analytics WebSocket message: {str(e)}")
                break
    
    except WebSocketDisconnect:
        logger.info(f"Analytics WebSocket disconnected for {dashboard_id}")
    except Exception as e:
        logger.error(f"Analytics WebSocket error for {dashboard_id}: {str(e)}")
    finally:
        await websocket_manager.disconnect(websocket)

# REST endpoints for WebSocket management
@router.get("/connections/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics.
    
    Returns:
        Dictionary with connection statistics
    """
    return await websocket_manager.get_connection_stats()

@router.post("/admin/broadcast")
async def broadcast_admin_notification(
    notification: dict,
    current_user: User = Depends(get_current_user)
):
    """
    Broadcast a notification to all admin connections.
    
    Args:
        notification: Notification data to broadcast
        current_user: Current authenticated user
    
    Returns:
        Success message
    """
    # Check if user has admin privileges
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    await websocket_manager.send_admin_notification(notification)
    
    return {"message": "Notification broadcasted successfully"}

@router.post("/cleanup")
async def cleanup_stale_connections(
    max_age_hours: int = 24,
    current_user: User = Depends(get_current_user)
):
    """
    Clean up stale WebSocket connections.
    
    Args:
        max_age_hours: Maximum age of connections in hours
        current_user: Current authenticated user
    
    Returns:
        Cleanup result
    """
    # Check if user has admin privileges
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    await websocket_manager.cleanup_stale_connections(max_age_hours)
    
    return {"message": "Stale connections cleaned up successfully"}