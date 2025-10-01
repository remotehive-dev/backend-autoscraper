from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
import threading

from backend.models.scraping_session import ScrapingSession, SessionStatus, SessionWebsite, WebsiteStatus
from backend.services.memory_loader import MemoryLoader, MemoryContext
from backend.services.scraper_orchestrator import ScraperOrchestrator, ScrapingConfig
from backend.services.web_scraper import WebScraperService
from backend.services.ml_service import MLService
from backend.database import get_db_session
# from sqlalchemy.orm import Session  # Using MongoDB instead

logger = logging.getLogger(__name__)

class SessionEventType(Enum):
    SESSION_CREATED = "session_created"
    SESSION_STARTED = "session_started"
    SESSION_PAUSED = "session_paused"
    SESSION_RESUMED = "session_resumed"
    SESSION_STOPPED = "session_stopped"
    SESSION_COMPLETED = "session_completed"
    SESSION_FAILED = "session_failed"
    WEBSITE_STARTED = "website_started"
    WEBSITE_COMPLETED = "website_completed"
    WEBSITE_FAILED = "website_failed"
    PROGRESS_UPDATE = "progress_update"
    ERROR_OCCURRED = "error_occurred"

@dataclass
class SessionEvent:
    event_type: SessionEventType
    session_id: int
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    website_id: Optional[int] = None
    message: Optional[str] = None

@dataclass
class SessionProgress:
    session_id: int
    total_websites: int
    completed_websites: int
    failed_websites: int
    in_progress_websites: int
    pending_websites: int
    progress_percentage: float
    estimated_completion: Optional[datetime]
    current_rate: float  # websites per minute
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

@dataclass
class SessionConfiguration:
    max_concurrent_websites: int = 5
    request_delay: float = 1.0
    timeout: int = 30
    retry_attempts: int = 3
    use_memory_context: bool = True
    memory_upload_id: Optional[int] = None
    enable_ml_optimization: bool = True
    screenshot_enabled: bool = False
    respect_robots_txt: bool = True
    custom_headers: Dict[str, str] = field(default_factory=dict)
    proxy_settings: Optional[Dict[str, str]] = None

class SessionManager:
    """Manages scraping sessions with comprehensive lifecycle control"""
    
    def __init__(self):
        self.active_sessions: Dict[int, ScrapingSession] = {}
        self.session_progress: Dict[int, SessionProgress] = {}
        self.event_callbacks: List[Callable[[SessionEvent], None]] = []
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.memory_loader = MemoryLoader()
        self.orchestrator = ScraperOrchestrator()
        self.web_scraper = WebScraperService()
        self.ml_service = None  # Initialize lazily when needed
        self._lock = threading.Lock()
        
        logger.info("SessionManager initialized")
    
    def _get_ml_service(self, db: Session = None) -> Optional[MLService]:
        """Get ML service instance, initializing lazily if needed"""
        if self.ml_service is None:
            try:
                if db is None:
                    with get_db_session() as db_session:
                        self.ml_service = MLService(db_session)
                else:
                    self.ml_service = MLService(db)
            except Exception as e:
                logger.warning(f"Failed to initialize ML service: {str(e)}")
                return None
        return self.ml_service
    
    def register_event_callback(self, callback: Callable[[SessionEvent], None]):
        """Register callback for session events"""
        self.event_callbacks.append(callback)
    
    def _emit_event(self, event: SessionEvent):
        """Emit session event to all registered callbacks"""
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event callback: {str(e)}")
    
    async def create_session(
        self,
        name: str,
        website_urls: List[str],
        user_id: int,
        config: SessionConfiguration,
        db: Session
    ) -> int:
        """Create a new scraping session"""
        try:
            # Create session record
            session = ScrapingSession(
                name=name,
                user_id=user_id,
                status=SessionStatus.CREATED,
                total_websites=len(website_urls),
                configuration=config.__dict__,
                created_at=datetime.utcnow()
            )
            
            db.add(session)
            db.commit()
            db.refresh(session)
            
            # Create website records
            for i, url in enumerate(website_urls):
                website = SessionWebsite(
                    session_id=session.id,
                    url=url,
                    order_index=i,
                    status=WebsiteStatus.PENDING
                )
                db.add(website)
            
            db.commit()
            
            # Initialize progress tracking
            progress = SessionProgress(
                session_id=session.id,
                total_websites=len(website_urls),
                completed_websites=0,
                failed_websites=0,
                in_progress_websites=0,
                pending_websites=len(website_urls),
                progress_percentage=0.0,
                estimated_completion=None,
                current_rate=0.0
            )
            
            with self._lock:
                self.active_sessions[session.id] = session
                self.session_progress[session.id] = progress
            
            # Load memory context if specified
            if config.use_memory_context and config.memory_upload_id:
                try:
                    memory_context = await self.memory_loader.get_memory_context(config.memory_upload_id)
                    if memory_context:
                        session.memory_context = memory_context.__dict__
                        db.commit()
                        logger.info(f"Loaded memory context for session {session.id}")
                except Exception as e:
                    logger.warning(f"Failed to load memory context: {str(e)}")
            
            # Emit event
            self._emit_event(SessionEvent(
                event_type=SessionEventType.SESSION_CREATED,
                session_id=session.id,
                timestamp=datetime.utcnow(),
                data={"name": name, "total_websites": len(website_urls)}
            ))
            
            logger.info(f"Created session {session.id} with {len(website_urls)} websites")
            return session.id
            
        except Exception as e:
            logger.error(f"Failed to create session: {str(e)}")
            raise
    
    async def start_session(self, session_id: int, db: Session) -> bool:
        """Start a scraping session"""
        try:
            session = db.query(ScrapingSession).filter(ScrapingSession.id == session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            if session.status != SessionStatus.CREATED:
                raise ValueError(f"Session {session_id} cannot be started (current status: {session.status})")
            
            # Update session status
            session.status = SessionStatus.RUNNING
            session.started_at = datetime.utcnow()
            db.commit()
            
            # Start processing in background
            self.executor.submit(self._process_session, session_id)
            
            # Emit event
            self._emit_event(SessionEvent(
                event_type=SessionEventType.SESSION_STARTED,
                session_id=session_id,
                timestamp=datetime.utcnow()
            ))
            
            logger.info(f"Started session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start session {session_id}: {str(e)}")
            return False
    
    async def pause_session(self, session_id: int, db: Session) -> bool:
        """Pause a running session"""
        try:
            session = db.query(ScrapingSession).filter(ScrapingSession.id == session_id).first()
            if not session:
                return False
            
            if session.status != SessionStatus.RUNNING:
                return False
            
            session.status = SessionStatus.PAUSED
            session.paused_at = datetime.utcnow()
            db.commit()
            
            # Emit event
            self._emit_event(SessionEvent(
                event_type=SessionEventType.SESSION_PAUSED,
                session_id=session_id,
                timestamp=datetime.utcnow()
            ))
            
            logger.info(f"Paused session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to pause session {session_id}: {str(e)}")
            return False
    
    async def resume_session(self, session_id: int, db: Session) -> bool:
        """Resume a paused session"""
        try:
            session = db.query(ScrapingSession).filter(ScrapingSession.id == session_id).first()
            if not session:
                return False
            
            if session.status != SessionStatus.PAUSED:
                return False
            
            session.status = SessionStatus.RUNNING
            session.resumed_at = datetime.utcnow()
            db.commit()
            
            # Resume processing
            self.executor.submit(self._process_session, session_id)
            
            # Emit event
            self._emit_event(SessionEvent(
                event_type=SessionEventType.SESSION_RESUMED,
                session_id=session_id,
                timestamp=datetime.utcnow()
            ))
            
            logger.info(f"Resumed session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to resume session {session_id}: {str(e)}")
            return False
    
    async def stop_session(self, session_id: int, db: Session) -> bool:
        """Stop a session"""
        try:
            session = db.query(ScrapingSession).filter(ScrapingSession.id == session_id).first()
            if not session:
                return False
            
            if session.status in [SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.STOPPED]:
                return True
            
            session.status = SessionStatus.STOPPED
            session.stopped_at = datetime.utcnow()
            db.commit()
            
            # Emit event
            self._emit_event(SessionEvent(
                event_type=SessionEventType.SESSION_STOPPED,
                session_id=session_id,
                timestamp=datetime.utcnow()
            ))
            
            logger.info(f"Stopped session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop session {session_id}: {str(e)}")
            return False
    
    def _process_session(self, session_id: int):
        """Process session in background thread"""
        try:
            with get_db_session() as db:
                session = db.query(ScrapingSession).filter(ScrapingSession.id == session_id).first()
                if not session:
                    return
                
                # Get session websites
                websites = db.query(SessionWebsite).filter(
                    SessionWebsite.session_id == session_id,
                    SessionWebsite.status.in_([WebsiteStatus.PENDING, WebsiteStatus.FAILED])
                ).order_by(SessionWebsite.order_index).all()
                
                config = SessionConfiguration(**session.configuration)
                
                # Process websites with concurrency control
                semaphore = asyncio.Semaphore(config.max_concurrent_websites)
                
                async def process_website(website: SessionWebsite):
                    async with semaphore:
                        await self._process_single_website(session_id, website, config, db)
                
                # Run async processing
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    tasks = [process_website(website) for website in websites]
                    loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                finally:
                    loop.close()
                
                # Update final session status
                self._finalize_session(session_id, db)
                
        except Exception as e:
            logger.error(f"Error processing session {session_id}: {str(e)}")
            self._handle_session_error(session_id, str(e))
    
    async def _process_single_website(self, session_id: int, website: SessionWebsite, config: SessionConfiguration, db: Session):
        """Process a single website"""
        try:
            # Check if session is still running
            session = db.query(ScrapingSession).filter(ScrapingSession.id == session_id).first()
            if not session or session.status not in [SessionStatus.RUNNING]:
                return
            
            # Update website status
            website.status = WebsiteStatus.IN_PROGRESS
            website.started_at = datetime.utcnow()
            db.commit()
            
            # Update progress
            self._update_progress(session_id, db)
            
            # Emit event
            self._emit_event(SessionEvent(
                event_type=SessionEventType.WEBSITE_STARTED,
                session_id=session_id,
                website_id=website.id,
                timestamp=datetime.utcnow(),
                data={"url": website.url}
            ))
            
            # Create scraping config
            scraping_config = ScrapingConfig(
                request_delay=config.request_delay,
                timeout=config.timeout,
                retry_attempts=config.retry_attempts,
                screenshot_enabled=config.screenshot_enabled,
                respect_robots_txt=config.respect_robots_txt,
                custom_headers=config.custom_headers
            )
            
            # Perform scraping
            result = await self.web_scraper.scrape_website(website.url, scraping_config)
            
            # Apply ML optimization if enabled
            if config.enable_ml_optimization and result.success:
                try:
                    ml_service = self._get_ml_service(db)
                    if ml_service:
                        optimized_result = await ml_service.optimize_extraction(website.url, result)
                        if optimized_result:
                            result = optimized_result
                except Exception as e:
                    logger.warning(f"ML optimization failed for {website.url}: {str(e)}")
            
            # Update website with results
            website.status = WebsiteStatus.COMPLETED if result.success else WebsiteStatus.FAILED
            website.completed_at = datetime.utcnow()
            website.extracted_data = result.data if result.success else None
            website.error_message = result.error if not result.success else None
            website.response_time = result.response_time
            website.status_code = result.status_code
            
            db.commit()
            
            # Emit completion event
            event_type = SessionEventType.WEBSITE_COMPLETED if result.success else SessionEventType.WEBSITE_FAILED
            self._emit_event(SessionEvent(
                event_type=event_type,
                session_id=session_id,
                website_id=website.id,
                timestamp=datetime.utcnow(),
                data={"url": website.url, "success": result.success}
            ))
            
            # Update progress
            self._update_progress(session_id, db)
            
            # Add delay between requests
            if config.request_delay > 0:
                await asyncio.sleep(config.request_delay)
                
        except Exception as e:
            logger.error(f"Error processing website {website.url}: {str(e)}")
            
            # Update website with error
            website.status = WebsiteStatus.FAILED
            website.completed_at = datetime.utcnow()
            website.error_message = str(e)
            db.commit()
            
            # Emit error event
            self._emit_event(SessionEvent(
                event_type=SessionEventType.WEBSITE_FAILED,
                session_id=session_id,
                website_id=website.id,
                timestamp=datetime.utcnow(),
                data={"url": website.url, "error": str(e)}
            ))
    
    def _update_progress(self, session_id: int, db: Session):
        """Update session progress"""
        try:
            # Get website counts
            website_counts = db.query(
                SessionWebsite.status,
                db.func.count(SessionWebsite.id)
            ).filter(
                SessionWebsite.session_id == session_id
            ).group_by(SessionWebsite.status).all()
            
            counts = {status.value: 0 for status in WebsiteStatus}
            for status, count in website_counts:
                counts[status.value] = count
            
            total = sum(counts.values())
            completed = counts[WebsiteStatus.COMPLETED.value]
            failed = counts[WebsiteStatus.FAILED.value]
            in_progress = counts[WebsiteStatus.IN_PROGRESS.value]
            pending = counts[WebsiteStatus.PENDING.value]
            
            progress_percentage = ((completed + failed) / total * 100) if total > 0 else 0
            
            # Calculate rate and ETA
            session = db.query(ScrapingSession).filter(ScrapingSession.id == session_id).first()
            current_rate = 0.0
            estimated_completion = None
            
            if session and session.started_at:
                elapsed_minutes = (datetime.utcnow() - session.started_at).total_seconds() / 60
                if elapsed_minutes > 0:
                    current_rate = (completed + failed) / elapsed_minutes
                    if current_rate > 0 and pending > 0:
                        eta_minutes = pending / current_rate
                        estimated_completion = datetime.utcnow() + timedelta(minutes=eta_minutes)
            
            # Update progress
            progress = SessionProgress(
                session_id=session_id,
                total_websites=total,
                completed_websites=completed,
                failed_websites=failed,
                in_progress_websites=in_progress,
                pending_websites=pending,
                progress_percentage=progress_percentage,
                estimated_completion=estimated_completion,
                current_rate=current_rate
            )
            
            with self._lock:
                self.session_progress[session_id] = progress
            
            # Update session record
            if session:
                session.completed_websites = completed
                session.failed_websites = failed
                session.progress_percentage = progress_percentage
                db.commit()
            
            # Emit progress event
            self._emit_event(SessionEvent(
                event_type=SessionEventType.PROGRESS_UPDATE,
                session_id=session_id,
                timestamp=datetime.utcnow(),
                data=progress.__dict__
            ))
            
        except Exception as e:
            logger.error(f"Error updating progress for session {session_id}: {str(e)}")
    
    def _finalize_session(self, session_id: int, db: Session):
        """Finalize session when processing is complete"""
        try:
            session = db.query(ScrapingSession).filter(ScrapingSession.id == session_id).first()
            if not session:
                return
            
            # Check if all websites are processed
            pending_count = db.query(SessionWebsite).filter(
                SessionWebsite.session_id == session_id,
                SessionWebsite.status == WebsiteStatus.PENDING
            ).count()
            
            if pending_count == 0 and session.status == SessionStatus.RUNNING:
                session.status = SessionStatus.COMPLETED
                session.completed_at = datetime.utcnow()
                
                # Calculate final metrics
                total_time = (session.completed_at - session.started_at).total_seconds() if session.started_at else 0
                session.total_duration = total_time
                
                db.commit()
                
                # Emit completion event
                self._emit_event(SessionEvent(
                    event_type=SessionEventType.SESSION_COMPLETED,
                    session_id=session_id,
                    timestamp=datetime.utcnow(),
                    data={"total_duration": total_time}
                ))
                
                logger.info(f"Session {session_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error finalizing session {session_id}: {str(e)}")
    
    def _handle_session_error(self, session_id: int, error_message: str):
        """Handle session-level errors"""
        try:
            with get_db_session() as db:
                session = db.query(ScrapingSession).filter(ScrapingSession.id == session_id).first()
                if session:
                    session.status = SessionStatus.FAILED
                    session.error_message = error_message
                    session.completed_at = datetime.utcnow()
                    db.commit()
            
            # Emit error event
            self._emit_event(SessionEvent(
                event_type=SessionEventType.SESSION_FAILED,
                session_id=session_id,
                timestamp=datetime.utcnow(),
                data={"error": error_message}
            ))
            
        except Exception as e:
            logger.error(f"Error handling session error for {session_id}: {str(e)}")
    
    def get_session_progress(self, session_id: int) -> Optional[SessionProgress]:
        """Get current session progress"""
        with self._lock:
            return self.session_progress.get(session_id)
    
    def get_active_sessions(self) -> List[int]:
        """Get list of active session IDs"""
        with self._lock:
            return list(self.active_sessions.keys())
    
    async def cleanup_completed_sessions(self, max_age_hours: int = 24):
        """Clean up old completed sessions from memory"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            with self._lock:
                sessions_to_remove = []
                for session_id, session in self.active_sessions.items():
                    if (session.status in [SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.STOPPED] and
                        session.completed_at and session.completed_at < cutoff_time):
                        sessions_to_remove.append(session_id)
                
                for session_id in sessions_to_remove:
                    del self.active_sessions[session_id]
                    if session_id in self.session_progress:
                        del self.session_progress[session_id]
            
            logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions")
            
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {str(e)}")
    
    def shutdown(self):
        """Shutdown session manager"""
        logger.info("Shutting down SessionManager")
        self.executor.shutdown(wait=True)
        self.web_scraper.cleanup()