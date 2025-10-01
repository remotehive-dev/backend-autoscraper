#!/usr/bin/env python3
"""
Job Queue System for Large-Scale Scraping Operations
Manages scraping tasks, priorities, and concurrent execution
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
import heapq
import uuid

# Import shared types
from .types import ScrapingResult, ScrapingStatus, JobPriority, QueuedJob
from .job_board_scrapers import JobBoardScraperFactory

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class TaskPriority(Enum):
    """Task priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class ScrapingTask:
    """Represents a scraping task in the queue"""
    id: str
    job_board: str
    query: str
    location: str
    max_pages: int
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    result: Optional[ScrapingResult] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for serialization"""
        data = asdict(self)
        # Convert enums to strings
        data['priority'] = self.priority.value
        data['status'] = self.status.value
        # Convert datetime objects to ISO strings
        for field in ['created_at', 'scheduled_at', 'started_at', 'completed_at']:
            if data[field]:
                data[field] = data[field].isoformat()
        # Convert result to dict if present
        if self.result:
            data['result'] = {
                'status': self.result.status.value,
                'jobs': self.result.jobs,
                'total_found': self.result.total_found,
                'pages_scraped': self.result.pages_scraped,
                'errors': self.result.errors,
                'execution_time': self.result.execution_time,
                'job_board_name': self.result.job_board_name,
                'timestamp': self.result.timestamp.isoformat()
            }
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScrapingTask':
        """Create task from dictionary"""
        # Convert string enums back to enum objects
        data['priority'] = TaskPriority(data['priority'])
        data['status'] = TaskStatus(data['status'])
        
        # Convert ISO strings back to datetime objects
        for field in ['created_at', 'scheduled_at', 'started_at', 'completed_at']:
            if data[field]:
                data[field] = datetime.fromisoformat(data[field])
        
        # Handle result conversion if present
        if data.get('result'):
            # This would need proper ScrapingResult reconstruction
            # For now, we'll skip it to avoid complexity
            data['result'] = None
        
        return cls(**data)

class JobQueue:
    """Async job queue for managing scraping tasks"""
    
    def __init__(self, max_concurrent_tasks: int = 5, 
                 max_queue_size: int = 1000):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_queue_size = max_queue_size
        
        # Task storage
        self.tasks: Dict[str, ScrapingTask] = {}
        self.pending_queue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self.running_tasks: Dict[str, asyncio.Task] = {}
        
        # Statistics
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'cancelled_tasks': 0,
            'total_jobs_scraped': 0
        }
        
        # Control flags
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []
        
        # Callbacks
        self.task_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
        logger.info(f"JobQueue initialized with max_concurrent_tasks={max_concurrent_tasks}")
    
    async def add_task(self, job_board: str, query: str = "remote", 
                      location: str = "Remote", max_pages: int = 3,
                      priority: TaskPriority = TaskPriority.NORMAL,
                      scheduled_at: Optional[datetime] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add a new scraping task to the queue"""
        
        if self.pending_queue.qsize() >= self.max_queue_size:
            raise Exception("Queue is full")
        
        task_id = str(uuid.uuid4())
        task = ScrapingTask(
            id=task_id,
            job_board=job_board,
            query=query,
            location=location,
            max_pages=max_pages,
            priority=priority,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            scheduled_at=scheduled_at,
            metadata=metadata or {}
        )
        
        self.tasks[task_id] = task
        
        # Add to priority queue (negative priority for correct ordering)
        priority_score = -priority.value
        if scheduled_at:
            # Add timestamp to priority for scheduled tasks
            priority_score += scheduled_at.timestamp() / 1000000
        
        await self.pending_queue.put((priority_score, task_id))
        self.stats['total_tasks'] += 1
        
        logger.info(f"Added task {task_id} for {job_board} with priority {priority.name}")
        return task_id
    
    async def add_bulk_tasks(self, tasks_config: List[Dict[str, Any]]) -> List[str]:
        """Add multiple tasks in bulk"""
        task_ids = []
        
        for config in tasks_config:
            task_id = await self.add_task(
                job_board=config['job_board'],
                query=config.get('query', 'remote'),
                location=config.get('location', 'Remote'),
                max_pages=config.get('max_pages', 3),
                priority=TaskPriority(config.get('priority', TaskPriority.NORMAL.value)),
                scheduled_at=config.get('scheduled_at'),
                metadata=config.get('metadata')
            )
            task_ids.append(task_id)
        
        logger.info(f"Added {len(task_ids)} tasks in bulk")
        return task_ids
    
    async def start_workers(self) -> None:
        """Start the worker tasks to process the queue"""
        if self._running:
            logger.warning("Workers are already running")
            return
        
        self._running = True
        
        # Start worker tasks
        for i in range(self.max_concurrent_tasks):
            worker_task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._worker_tasks.append(worker_task)
        
        logger.info(f"Started {self.max_concurrent_tasks} worker tasks")
    
    async def stop_workers(self) -> None:
        """Stop all worker tasks"""
        self._running = False
        
        # Cancel all worker tasks
        for task in self._worker_tasks:
            task.cancel()
        
        # Wait for workers to finish
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        # Cancel running scraping tasks
        for task_id, running_task in self.running_tasks.items():
            running_task.cancel()
            self.tasks[task_id].status = TaskStatus.CANCELLED
            self.stats['cancelled_tasks'] += 1
        
        self._worker_tasks.clear()
        self.running_tasks.clear()
        
        logger.info("All workers stopped")
    
    async def _worker(self, worker_name: str) -> None:
        """Worker task that processes jobs from the queue"""
        logger.info(f"Worker {worker_name} started")
        
        while self._running:
            try:
                # Get next task from queue with timeout
                try:
                    priority_score, task_id = await asyncio.wait_for(
                        self.pending_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                task = self.tasks.get(task_id)
                if not task:
                    logger.warning(f"Task {task_id} not found")
                    continue
                
                # Check if task is scheduled for future
                if task.scheduled_at and task.scheduled_at > datetime.now():
                    # Put it back in queue for later
                    await self.pending_queue.put((priority_score, task_id))
                    await asyncio.sleep(1)
                    continue
                
                # Execute the task
                await self._execute_task(task, worker_name)
                
            except asyncio.CancelledError:
                logger.info(f"Worker {worker_name} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Worker {worker_name} stopped")
    
    async def _execute_task(self, task: ScrapingTask, worker_name: str) -> None:
        """Execute a single scraping task"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        logger.info(f"Worker {worker_name} executing task {task.id} for {task.job_board}")
        
        try:
            # Create scraper for the job board
            scraper = JobBoardScraperFactory.create_scraper(task.job_board)
            if not scraper:
                raise Exception(f"No scraper available for {task.job_board}")
            
            # Create and store the running task
            scraping_task = asyncio.create_task(
                self._run_scraping_task(scraper, task)
            )
            self.running_tasks[task.id] = scraping_task
            
            # Wait for completion
            result = await scraping_task
            
            # Update task with result
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            # Update statistics
            self.stats['completed_tasks'] += 1
            if result and result.jobs:
                self.stats['total_jobs_scraped'] += len(result.jobs)
            
            logger.info(f"Task {task.id} completed successfully. Found {len(result.jobs) if result else 0} jobs")
            
            # Execute callbacks
            await self._execute_callbacks(task.id, 'completed', task)
            
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            self.stats['cancelled_tasks'] += 1
            logger.info(f"Task {task.id} was cancelled")
            
        except Exception as e:
            task.error = str(e)
            task.retry_count += 1
            
            # Retry logic
            if task.retry_count <= task.max_retries:
                task.status = TaskStatus.RETRYING
                logger.warning(f"Task {task.id} failed (attempt {task.retry_count}/{task.max_retries}): {e}")
                
                # Add back to queue with delay
                retry_delay = min(2 ** task.retry_count, 60)  # Exponential backoff, max 60s
                await asyncio.sleep(retry_delay)
                
                priority_score = -task.priority.value
                await self.pending_queue.put((priority_score, task.id))
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                self.stats['failed_tasks'] += 1
                logger.error(f"Task {task.id} failed permanently after {task.retry_count} attempts: {e}")
                
                # Execute callbacks
                await self._execute_callbacks(task.id, 'failed', task)
        
        finally:
            # Remove from running tasks
            self.running_tasks.pop(task.id, None)
    
    async def _run_scraping_task(self, scraper, task: ScrapingTask) -> ScrapingResult:
        """Run the actual scraping operation"""
        async with scraper:
            return await scraper.scrape_jobs(
                query=task.query,
                location=task.location,
                max_pages=task.max_pages
            )
    
    async def _execute_callbacks(self, task_id: str, event: str, task: ScrapingTask) -> None:
        """Execute registered callbacks for task events"""
        callbacks = self.task_callbacks.get(event, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task)
                else:
                    callback(task)
            except Exception as e:
                logger.error(f"Callback error for task {task_id}: {e}")
    
    def add_callback(self, event: str, callback: Callable) -> None:
        """Add a callback for task events (completed, failed, etc.)"""
        self.task_callbacks[event].append(callback)
    
    async def get_task(self, task_id: str) -> Optional[ScrapingTask]:
        """Get task by ID"""
        return self.tasks.get(task_id)
    
    async def get_tasks_by_status(self, status: TaskStatus) -> List[ScrapingTask]:
        """Get all tasks with specific status"""
        return [task for task in self.tasks.values() if task.status == status]
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a specific task"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.status == TaskStatus.RUNNING:
            running_task = self.running_tasks.get(task_id)
            if running_task:
                running_task.cancel()
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        self.stats['cancelled_tasks'] += 1
        
        logger.info(f"Task {task_id} cancelled")
        return True
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get current queue status and statistics"""
        status_counts = defaultdict(int)
        for task in self.tasks.values():
            status_counts[task.status.value] += 1
        
        return {
            'queue_size': self.pending_queue.qsize(),
            'running_tasks': len(self.running_tasks),
            'total_tasks': len(self.tasks),
            'status_counts': dict(status_counts),
            'statistics': self.stats.copy(),
            'workers_running': self._running,
            'max_concurrent_tasks': self.max_concurrent_tasks
        }
    
    async def clear_completed_tasks(self, older_than_hours: int = 24) -> int:
        """Clear completed tasks older than specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        
        tasks_to_remove = []
        for task_id, task in self.tasks.items():
            if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] and
                task.completed_at and task.completed_at < cutoff_time):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
        
        logger.info(f"Cleared {len(tasks_to_remove)} old completed tasks")
        return len(tasks_to_remove)

class ScheduledJobManager:
    """Manager for scheduled recurring scraping jobs"""
    
    def __init__(self, job_queue: JobQueue):
        self.job_queue = job_queue
        self.scheduled_jobs: Dict[str, Dict[str, Any]] = {}
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False
    
    def add_recurring_job(self, name: str, job_board: str, 
                         interval_hours: int = 24,
                         query: str = "remote", location: str = "Remote",
                         max_pages: int = 3,
                         priority: TaskPriority = TaskPriority.NORMAL) -> None:
        """Add a recurring scraping job"""
        
        self.scheduled_jobs[name] = {
            'job_board': job_board,
            'interval_hours': interval_hours,
            'query': query,
            'location': location,
            'max_pages': max_pages,
            'priority': priority,
            'last_run': None,
            'next_run': datetime.now()
        }
        
        logger.info(f"Added recurring job '{name}' for {job_board} every {interval_hours} hours")
    
    async def start_scheduler(self) -> None:
        """Start the job scheduler"""
        if self._running:
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Job scheduler started")
    
    async def stop_scheduler(self) -> None:
        """Stop the job scheduler"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Job scheduler stopped")
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop"""
        while self._running:
            try:
                now = datetime.now()
                
                for name, job_config in self.scheduled_jobs.items():
                    if now >= job_config['next_run']:
                        # Schedule the job
                        await self.job_queue.add_task(
                            job_board=job_config['job_board'],
                            query=job_config['query'],
                            location=job_config['location'],
                            max_pages=job_config['max_pages'],
                            priority=job_config['priority'],
                            metadata={'scheduled_job': name}
                        )
                        
                        # Update next run time
                        job_config['last_run'] = now
                        job_config['next_run'] = now + timedelta(hours=job_config['interval_hours'])
                        
                        logger.info(f"Scheduled job '{name}' added to queue. Next run: {job_config['next_run']}")
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(60)

# Global job queue instance
_global_job_queue: Optional[JobQueue] = None

def get_job_queue() -> JobQueue:
    """Get or create the global job queue instance"""
    global _global_job_queue
    if _global_job_queue is None:
        _global_job_queue = JobQueue()
    return _global_job_queue

# Convenience functions
async def queue_scraping_task(job_board: str, query: str = "remote", 
                             location: str = "Remote", max_pages: int = 3,
                             priority: TaskPriority = TaskPriority.NORMAL) -> str:
    """Queue a single scraping task"""
    queue = get_job_queue()
    return await queue.add_task(job_board, query, location, max_pages, priority)

async def queue_multiple_job_boards(query: str = "remote", 
                                   location: str = "Remote",
                                   max_pages: int = 3) -> List[str]:
    """Queue scraping tasks for all available job boards"""
    queue = get_job_queue()
    available_scrapers = JobBoardScraperFactory.get_available_scrapers()
    
    task_ids = []
    for job_board in available_scrapers:
        task_id = await queue.add_task(job_board, query, location, max_pages)
        task_ids.append(task_id)
    
    return task_ids