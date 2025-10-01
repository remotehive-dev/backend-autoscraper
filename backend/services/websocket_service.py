import asyncio
import json
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    WebSocket manager for real-time updates in the admin interface.
    Handles connections for CSV import progress, scraper status, and analytics.
    """
    
    def __init__(self):
        # Store active connections by type and identifier
        self.connections: Dict[str, Dict[str, Set[WebSocket]]] = {
            'csv_import': {},  # upload_id -> set of websockets
            'scraper_status': {},  # scraper_id -> set of websockets
            'analytics': {},  # dashboard_id -> set of websockets
            'admin_general': set()  # general admin notifications
        }
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(
        self,
        websocket: WebSocket,
        connection_type: str,
        identifier: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            connection_type: Type of connection (csv_import, scraper_status, analytics, admin_general)
            identifier: Specific identifier (upload_id, scraper_id, dashboard_id)
            user_id: ID of the connected user
        """
        await websocket.accept()
        
        # Store connection metadata
        self.connection_metadata[websocket] = {
            'type': connection_type,
            'identifier': identifier,
            'user_id': user_id,
            'connected_at': datetime.utcnow()
        }
        
        # Add to appropriate connection group
        if connection_type == 'admin_general':
            self.connections['admin_general'].add(websocket)
        else:
            if identifier:
                if identifier not in self.connections[connection_type]:
                    self.connections[connection_type][identifier] = set()
                self.connections[connection_type][identifier].add(websocket)
        
        logger.info(f"WebSocket connected: {connection_type}:{identifier} for user {user_id}")
        
        # Send initial connection confirmation
        await self.send_to_connection(websocket, {
            'type': 'connection_established',
            'connection_type': connection_type,
            'identifier': identifier,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    async def disconnect(self, websocket: WebSocket):
        """
        Handle WebSocket disconnection.
        
        Args:
            websocket: WebSocket connection to disconnect
        """
        if websocket not in self.connection_metadata:
            return
        
        metadata = self.connection_metadata[websocket]
        connection_type = metadata['type']
        identifier = metadata['identifier']
        
        # Remove from connection groups
        if connection_type == 'admin_general':
            self.connections['admin_general'].discard(websocket)
        else:
            if identifier and identifier in self.connections[connection_type]:
                self.connections[connection_type][identifier].discard(websocket)
                # Clean up empty groups
                if not self.connections[connection_type][identifier]:
                    del self.connections[connection_type][identifier]
        
        # Remove metadata
        del self.connection_metadata[websocket]
        
        logger.info(f"WebSocket disconnected: {connection_type}:{identifier}")
    
    async def send_to_connection(self, websocket: WebSocket, data: Dict[str, Any]):
        """
        Send data to a specific WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            data: Data to send
        """
        try:
            await websocket.send_text(json.dumps(data))
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {str(e)}")
            await self.disconnect(websocket)
    
    async def broadcast_to_type(
        self,
        connection_type: str,
        identifier: Optional[str],
        data: Dict[str, Any]
    ):
        """
        Broadcast data to all connections of a specific type.
        
        Args:
            connection_type: Type of connections to broadcast to
            identifier: Specific identifier (optional)
            data: Data to broadcast
        """
        if connection_type == 'admin_general':
            connections = list(self.connections['admin_general'])
        else:
            if not identifier or identifier not in self.connections[connection_type]:
                return
            connections = list(self.connections[connection_type][identifier])
        
        # Send to all connections
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_text(json.dumps(data))
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {str(e)}")
                disconnected.append(websocket)
        
        # Clean up disconnected sockets
        for websocket in disconnected:
            await self.disconnect(websocket)
    
    async def send_csv_import_update(
        self,
        upload_id: str,
        progress_data: Dict[str, Any]
    ):
        """
        Send CSV import progress update to connected clients.
        
        Args:
            upload_id: Upload identifier
            progress_data: Progress information
        """
        message = {
            'type': 'csv_import_progress',
            'upload_id': upload_id,
            'data': progress_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_type('csv_import', upload_id, message)
    
    async def send_scraper_status_update(
        self,
        scraper_id: str,
        status_data: Dict[str, Any]
    ):
        """
        Send scraper status update to connected clients.
        
        Args:
            scraper_id: Scraper identifier
            status_data: Status information
        """
        message = {
            'type': 'scraper_status_update',
            'scraper_id': scraper_id,
            'data': status_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_type('scraper_status', scraper_id, message)
    
    async def send_analytics_update(
        self,
        dashboard_id: str,
        analytics_data: Dict[str, Any]
    ):
        """
        Send analytics update to connected clients.
        
        Args:
            dashboard_id: Dashboard identifier
            analytics_data: Analytics information
        """
        message = {
            'type': 'analytics_update',
            'dashboard_id': dashboard_id,
            'data': analytics_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_type('analytics', dashboard_id, message)
    
    async def send_admin_notification(
        self,
        notification_data: Dict[str, Any]
    ):
        """
        Send general admin notification to all admin connections.
        
        Args:
            notification_data: Notification information
        """
        message = {
            'type': 'admin_notification',
            'data': notification_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_type('admin_general', None, message)
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about active WebSocket connections.
        
        Returns:
            Dictionary with connection statistics
        """
        stats = {
            'total_connections': len(self.connection_metadata),
            'by_type': {},
            'active_imports': len(self.connections['csv_import']),
            'active_scrapers': len(self.connections['scraper_status']),
            'active_dashboards': len(self.connections['analytics']),
            'admin_connections': len(self.connections['admin_general'])
        }
        
        # Count connections by type
        for websocket, metadata in self.connection_metadata.items():
            conn_type = metadata['type']
            if conn_type not in stats['by_type']:
                stats['by_type'][conn_type] = 0
            stats['by_type'][conn_type] += 1
        
        return stats
    
    async def cleanup_stale_connections(self, max_age_hours: int = 24):
        """
        Clean up stale WebSocket connections.
        
        Args:
            max_age_hours: Maximum age of connections in hours
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        stale_connections = []
        
        for websocket, metadata in self.connection_metadata.items():
            if metadata['connected_at'] < cutoff_time:
                stale_connections.append(websocket)
        
        for websocket in stale_connections:
            await self.disconnect(websocket)
        
        logger.info(f"Cleaned up {len(stale_connections)} stale WebSocket connections")

# Global WebSocket manager instance
websocket_manager = WebSocketManager()

class CSVImportWebSocketHandler:
    """
    Handler for CSV import WebSocket connections.
    """
    
    def __init__(self, progress_tracker):
        self.progress_tracker = progress_tracker
    
    async def handle_connection(
        self,
        websocket: WebSocket,
        upload_id: str,
        user_id: str
    ):
        """
        Handle a CSV import WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            upload_id: Upload identifier to track
            user_id: ID of the connected user
        """
        await websocket_manager.connect(
            websocket=websocket,
            connection_type='csv_import',
            identifier=upload_id,
            user_id=user_id
        )
        
        # Register progress callback
        async def progress_callback(progress_data):
            await websocket_manager.send_csv_import_update(upload_id, progress_data)
        
        await self.progress_tracker.register_progress_callback(upload_id, progress_callback)
        
        try:
            # Send initial progress data
            initial_progress = await self.progress_tracker.get_import_progress(upload_id)
            await websocket_manager.send_csv_import_update(upload_id, initial_progress)
            
            # Keep connection alive and handle messages
            while True:
                try:
                    # Wait for messages (ping/pong, status requests, etc.)
                    message = await websocket.receive_text()
                    data = json.loads(message)
                    
                    if data.get('type') == 'get_progress':
                        progress = await self.progress_tracker.get_import_progress(upload_id)
                        await websocket_manager.send_csv_import_update(upload_id, progress)
                    
                    elif data.get('type') == 'get_logs':
                        logs = await self.progress_tracker.get_recent_logs(
                            upload_id=upload_id,
                            limit=data.get('limit', 50),
                            status_filter=data.get('status_filter')
                        )
                        await websocket_manager.send_to_connection(websocket, {
                            'type': 'import_logs',
                            'upload_id': upload_id,
                            'logs': logs
                        })
                    
                    elif data.get('type') == 'cancel_import':
                        success = await self.progress_tracker.cancel_import(
                            upload_id=upload_id,
                            reason='Cancelled via WebSocket'
                        )
                        await websocket_manager.send_to_connection(websocket, {
                            'type': 'cancel_result',
                            'upload_id': upload_id,
                            'success': success
                        })
                
                except WebSocketDisconnect:
                    break
                except json.JSONDecodeError:
                    await websocket_manager.send_to_connection(websocket, {
                        'type': 'error',
                        'message': 'Invalid JSON message'
                    })
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {str(e)}")
                    await websocket_manager.send_to_connection(websocket, {
                        'type': 'error',
                        'message': 'Internal server error'
                    })
        
        finally:
            # Cleanup
            await self.progress_tracker.unregister_progress_callback(upload_id, progress_callback)
            await websocket_manager.disconnect(websocket)