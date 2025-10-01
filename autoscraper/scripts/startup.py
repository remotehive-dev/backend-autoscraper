#!/usr/bin/env python3
"""
AutoScraper Service Startup Script
Dedicated startup script for the autoscraper service with health checks
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from typing import Optional
import requests
from loguru import logger

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.settings import get_settings

settings = get_settings()

class AutoScraperStarter:
    """AutoScraper service startup manager"""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.service_url = f"http://{settings.HOST}:{settings.PORT}"
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def check_dependencies(self) -> bool:
        """Check if required dependencies are available"""
        logger.info("Checking dependencies...")
        
        # Check Redis connection
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            r.ping()
            logger.info("✓ Redis connection successful")
        except Exception as e:
            logger.warning(f"⚠ Redis not available: {e}")
            logger.info("AutoScraper will run with limited functionality")
        
        # Check database connection
        try:
            from app.database.database import DatabaseManager
            db_manager = DatabaseManager()
            logger.info("✓ Database configuration loaded")
        except Exception as e:
            logger.error(f"✗ Database configuration failed: {e}")
            return False
        
        return True
    
    def start(self) -> bool:
        """Start the autoscraper service"""
        logger.info("Starting AutoScraper Service...")
        
        if not self.check_dependencies():
            logger.error("Dependency check failed")
            return False
        
        # Start the service
        cmd = [
            sys.executable, "-m", "uvicorn", 
            "app.main:app",
            "--host", settings.HOST,
            "--port", str(settings.PORT),
            "--reload" if settings.ENVIRONMENT == "development" else "--no-reload"
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            logger.info(f"Service started with PID: {self.process.pid}")
            
            # Wait for service to be ready
            if self.wait_for_health():
                logger.info(f"✓ AutoScraper Service is ready at {self.service_url}")
                return True
            else:
                logger.error("Service failed to start properly")
                self.stop()
                return False
                
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            return False
    
    def wait_for_health(self, timeout: int = 30) -> bool:
        """Wait for service to be healthy"""
        logger.info("Waiting for service to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.service_url}/health", timeout=5)
                if response.status_code == 200:
                    return True
            except requests.RequestException:
                pass
            
            time.sleep(2)
        
        return False
    
    def stop(self):
        """Stop the autoscraper service"""
        if self.process:
            logger.info("Stopping AutoScraper Service...")
            self.process.terminate()
            
            # Wait for graceful shutdown
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Force killing service...")
                self.process.kill()
                self.process.wait()
            
            logger.info("Service stopped")
    
    def run(self):
        """Run the service and wait"""
        if self.start():
            try:
                # Keep the service running
                self.process.wait()
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
            finally:
                self.stop()
        else:
            sys.exit(1)

def main():
    """Main entry point"""
    starter = AutoScraperStarter()
    starter.run()

if __name__ == "__main__":
    main()