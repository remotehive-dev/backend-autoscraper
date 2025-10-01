import json
import redis
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from backend.database.mongodb_models import ScraperState, ScraperConfig
import logging

logger = logging.getLogger(__name__)

class RedisStateManager:
    """Redis-based state management for scraper operations"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", db: int = 0):
        self.redis_client = redis.Redis.from_url(redis_url, db=db, decode_responses=True)
        self.state_prefix = "scraper_state:"
        self.lock_prefix = "scraper_lock:"
        self.metrics_prefix = "scraper_metrics:"
        
    async def connect(self) -> bool:
        """Test Redis connection"""
        try:
            self.redis_client.ping()
            logger.info("Redis connection established successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False
    
    def _get_state_key(self, scraper_id: int) -> str:
        """Generate Redis key for scraper state"""
        return f"{self.state_prefix}{scraper_id}"
    
    def _get_lock_key(self, scraper_id: int) -> str:
        """Generate Redis key for scraper lock"""
        return f"{self.lock_prefix}{scraper_id}"
    
    def _get_metrics_key(self, scraper_id: int) -> str:
        """Generate Redis key for scraper metrics"""
        return f"{self.metrics_prefix}{scraper_id}"
    
    async def set_scraper_state(self, scraper_id: int, state_data: Dict[str, Any], ttl: int = 3600) -> bool:
        """Set scraper state in Redis with TTL"""
        try:
            key = self._get_state_key(scraper_id)
            state_data['last_updated'] = datetime.now().isoformat()
            state_data['scraper_id'] = scraper_id
            
            # Store in Redis
            self.redis_client.setex(key, ttl, json.dumps(state_data))
            
            # Also backup to database
            await self._backup_state_to_db(scraper_id, state_data)
            
            logger.info(f"State set for scraper {scraper_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to set state for scraper {scraper_id}: {e}")
            return False
    
    async def get_scraper_state(self, scraper_id: int) -> Optional[Dict[str, Any]]:
        """Get scraper state from Redis, fallback to database"""
        try:
            key = self._get_state_key(scraper_id)
            state_json = self.redis_client.get(key)
            
            if state_json:
                return json.loads(state_json)
            
            # Fallback to database
            return await self._get_state_from_db(scraper_id)
            
        except Exception as e:
            logger.error(f"Failed to get state for scraper {scraper_id}: {e}")
            return None
    
    async def update_scraper_progress(self, scraper_id: int, current_page: int, processed_urls: List[str]) -> bool:
        """Update scraper progress in real-time"""
        try:
            current_state = await self.get_scraper_state(scraper_id) or {}
            current_state.update({
                'current_page': current_page,
                'processed_urls': processed_urls,
                'total_processed': len(processed_urls),
                'last_updated': datetime.now().isoformat()
            })
            
            return await self.set_scraper_state(scraper_id, current_state)
        except Exception as e:
            logger.error(f"Failed to update progress for scraper {scraper_id}: {e}")
            return False
    
    async def pause_scraper(self, scraper_id: int) -> bool:
        """Pause scraper execution"""
        try:
            current_state = await self.get_scraper_state(scraper_id) or {}
            current_state.update({
                'current_state': 'paused',
                'is_paused': True,
                'paused_at': datetime.now().isoformat()
            })
            
            return await self.set_scraper_state(scraper_id, current_state)
        except Exception as e:
            logger.error(f"Failed to pause scraper {scraper_id}: {e}")
            return False
    
    async def resume_scraper(self, scraper_id: int) -> bool:
        """Resume scraper execution"""
        try:
            current_state = await self.get_scraper_state(scraper_id) or {}
            current_state.update({
                'current_state': 'running',
                'is_paused': False,
                'resumed_at': datetime.now().isoformat()
            })
            
            return await self.set_scraper_state(scraper_id, current_state)
        except Exception as e:
            logger.error(f"Failed to resume scraper {scraper_id}: {e}")
            return False
    
    async def stop_scraper(self, scraper_id: int) -> bool:
        """Stop scraper execution and clean up state"""
        try:
            current_state = await self.get_scraper_state(scraper_id) or {}
            current_state.update({
                'current_state': 'stopped',
                'is_paused': False,
                'stopped_at': datetime.now().isoformat()
            })
            
            # Set final state
            await self.set_scraper_state(scraper_id, current_state)
            
            # Clean up Redis keys after a delay
            await asyncio.sleep(1)
            await self._cleanup_scraper_keys(scraper_id)
            
            return True
        except Exception as e:
            logger.error(f"Failed to stop scraper {scraper_id}: {e}")
            return False
    
    async def acquire_scraper_lock(self, scraper_id: int, timeout: int = 300) -> bool:
        """Acquire distributed lock for scraper"""
        try:
            lock_key = self._get_lock_key(scraper_id)
            lock_value = f"lock_{scraper_id}_{datetime.now().timestamp()}"
            
            # Try to acquire lock with timeout
            result = self.redis_client.set(lock_key, lock_value, nx=True, ex=timeout)
            
            if result:
                logger.info(f"Lock acquired for scraper {scraper_id}")
                return True
            else:
                logger.warning(f"Failed to acquire lock for scraper {scraper_id} - already locked")
                return False
                
        except Exception as e:
            logger.error(f"Failed to acquire lock for scraper {scraper_id}: {e}")
            return False
    
    async def release_scraper_lock(self, scraper_id: int) -> bool:
        """Release distributed lock for scraper"""
        try:
            lock_key = self._get_lock_key(scraper_id)
            result = self.redis_client.delete(lock_key)
            
            if result:
                logger.info(f"Lock released for scraper {scraper_id}")
                return True
            else:
                logger.warning(f"No lock found to release for scraper {scraper_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to release lock for scraper {scraper_id}: {e}")
            return False
    
    async def set_scraper_metrics(self, scraper_id: int, metrics: Dict[str, Any]) -> bool:
        """Store real-time scraper metrics"""
        try:
            key = self._get_metrics_key(scraper_id)
            metrics['timestamp'] = datetime.now().isoformat()
            metrics['scraper_id'] = scraper_id
            
            # Store with 1 hour TTL
            self.redis_client.setex(key, 3600, json.dumps(metrics))
            
            logger.debug(f"Metrics updated for scraper {scraper_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to set metrics for scraper {scraper_id}: {e}")
            return False
    
    async def get_scraper_metrics(self, scraper_id: int) -> Optional[Dict[str, Any]]:
        """Get real-time scraper metrics"""
        try:
            key = self._get_metrics_key(scraper_id)
            metrics_json = self.redis_client.get(key)
            
            if metrics_json:
                return json.loads(metrics_json)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get metrics for scraper {scraper_id}: {e}")
            return None
    
    async def get_all_active_scrapers(self) -> List[int]:
        """Get list of all active scraper IDs"""
        try:
            pattern = f"{self.state_prefix}*"
            keys = self.redis_client.keys(pattern)
            
            scraper_ids = []
            for key in keys:
                try:
                    scraper_id = int(key.replace(self.state_prefix, ""))
                    scraper_ids.append(scraper_id)
                except ValueError:
                    continue
            
            return scraper_ids
        except Exception as e:
            logger.error(f"Failed to get active scrapers: {e}")
            return []
    
    async def _backup_state_to_db(self, scraper_id: str, state_data: Dict[str, Any]):
        """Backup state to database for persistence"""
        try:
            # Find or create scraper state record
            scraper_state = await ScraperState.find_one(
                ScraperState.scraper_config_id == scraper_id
            )
            
            if not scraper_state:
                scraper_state = ScraperState(
                    scraper_config_id=scraper_id,
                    redis_key=self._get_state_key(scraper_id)
                )
            
            # Update state data
            scraper_state.current_state = state_data.get('current_state', 'idle')
            scraper_state.state_data = state_data
            scraper_state.is_paused = state_data.get('is_paused', False)
            scraper_state.current_page = state_data.get('current_page', 0)
            scraper_state.processed_urls = state_data.get('processed_urls', [])
            scraper_state.last_updated = datetime.utcnow()
            scraper_state.updated_at = datetime.utcnow()
            
            await scraper_state.save()
            
        except Exception as e:
            logger.error(f"Failed to backup state to database for scraper {scraper_id}: {e}")
    
    async def _get_state_from_db(self, scraper_id: str) -> Optional[Dict[str, Any]]:
        """Get state from database as fallback"""
        try:
            scraper_state = await ScraperState.find_one(
                ScraperState.scraper_config_id == scraper_id
            )
            
            if scraper_state:
                return {
                    'scraper_id': scraper_id,
                    'current_state': scraper_state.current_state,
                    'state_data': scraper_state.state_data or {},
                    'is_paused': scraper_state.is_paused,
                    'current_page': scraper_state.current_page,
                    'processed_urls': scraper_state.processed_urls or [],
                    'last_updated': scraper_state.last_updated.isoformat() if scraper_state.last_updated else None
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get state from database for scraper {scraper_id}: {e}")
            return None
    
    async def _cleanup_scraper_keys(self, scraper_id: int):
        """Clean up all Redis keys for a scraper"""
        try:
            keys_to_delete = [
                self._get_state_key(scraper_id),
                self._get_lock_key(scraper_id),
                self._get_metrics_key(scraper_id)
            ]
            
            for key in keys_to_delete:
                self.redis_client.delete(key)
            
            logger.info(f"Cleaned up Redis keys for scraper {scraper_id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup keys for scraper {scraper_id}: {e}")


# Global Redis state manager instance
redis_state_manager = RedisStateManager()