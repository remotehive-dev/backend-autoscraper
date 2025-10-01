#!/usr/bin/env python3
"""
AutoScraper Service Management Utilities
Provides utilities for starting, stopping, and managing the AutoScraper service
"""

import os
import sys
import time
import signal
import psutil
import subprocess
import json
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

# Configuration
SERVICE_NAME = "autoscraper-service"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8001
DEFAULT_WORKERS = 1
HEALTH_CHECK_URL = f"http://localhost:{DEFAULT_PORT}/health"
PID_FILE = "/tmp/autoscraper-service.pid"
LOG_FILE = "/tmp/autoscraper-service.log"
MAX_STARTUP_TIME = 30  # seconds
MAX_SHUTDOWN_TIME = 15  # seconds

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ServiceManager:
    """AutoScraper service management class"""
    
    def __init__(self, service_dir: Optional[str] = None):
        self.service_dir = Path(service_dir) if service_dir else Path(__file__).parent.parent
        self.app_dir = self.service_dir / "app"
        self.pid_file = Path(PID_FILE)
        self.log_file = Path(LOG_FILE)
        
        # Ensure directories exist
        self.service_dir.mkdir(exist_ok=True)
        self.app_dir.mkdir(exist_ok=True)
    
    def _get_service_pid(self) -> Optional[int]:
        """Get the PID of the running service"""
        if not self.pid_file.exists():
            return None
        
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is actually running
            if psutil.pid_exists(pid):
                process = psutil.Process(pid)
                # Verify it's our service by checking command line
                cmdline = ' '.join(process.cmdline())
                if 'uvicorn' in cmdline and 'autoscraper' in cmdline:
                    return pid
            
            # PID file exists but process is not running, clean up
            self.pid_file.unlink()
            return None
            
        except (ValueError, FileNotFoundError, psutil.NoSuchProcess):
            return None
    
    def _save_pid(self, pid: int):
        """Save process PID to file"""
        with open(self.pid_file, 'w') as f:
            f.write(str(pid))
    
    def _remove_pid_file(self):
        """Remove PID file"""
        if self.pid_file.exists():
            self.pid_file.unlink()
    
    def _check_dependencies(self) -> Dict[str, bool]:
        """Check if required dependencies are available"""
        dependencies = {
            "redis": self._check_redis(),
            "python_packages": self._check_python_packages(),
            "app_files": self._check_app_files()
        }
        return dependencies
    
    def _check_redis(self) -> bool:
        """Check if Redis is available"""
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            r.ping()
            return True
        except Exception:
            return False
    
    def _check_python_packages(self) -> bool:
        """Check if required Python packages are installed"""
        required_packages = ['fastapi', 'uvicorn', 'redis', 'celery', 'sqlalchemy']
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                logger.error(f"Required package '{package}' is not installed")
                return False
        return True
    
    def _check_app_files(self) -> bool:
        """Check if required application files exist"""
        required_files = [
            self.app_dir / "main.py",
            self.app_dir / "api" / "autoscraper.py"
        ]
        
        for file_path in required_files:
            if not file_path.exists():
                logger.error(f"Required file '{file_path}' does not exist")
                return False
        return True
    
    def _wait_for_health_check(self, timeout: int = MAX_STARTUP_TIME) -> bool:
        """Wait for service to become healthy"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(HEALTH_CHECK_URL, timeout=5)
                if response.status_code == 200:
                    return True
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(1)
        
        return False
    
    def start(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, 
              workers: int = DEFAULT_WORKERS, background: bool = True) -> Dict[str, Any]:
        """Start the AutoScraper service"""
        logger.info(f"Starting {SERVICE_NAME}...")
        
        # Check if already running
        existing_pid = self._get_service_pid()
        if existing_pid:
            return {
                "success": False,
                "message": f"Service is already running with PID {existing_pid}",
                "pid": existing_pid
            }
        
        # Check dependencies
        deps = self._check_dependencies()
        failed_deps = [dep for dep, status in deps.items() if not status]
        
        if failed_deps:
            return {
                "success": False,
                "message": f"Missing dependencies: {', '.join(failed_deps)}",
                "dependencies": deps
            }
        
        # Prepare command
        cmd = [
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", host,
            "--port", str(port),
            "--workers", str(workers)
        ]
        
        try:
            # Start the service
            if background:
                # Start as background process
                with open(self.log_file, 'w') as log_f:
                    process = subprocess.Popen(
                        cmd,
                        cwd=self.service_dir,
                        stdout=log_f,
                        stderr=subprocess.STDOUT,
                        start_new_session=True
                    )
                
                # Save PID
                self._save_pid(process.pid)
                
                # Wait for service to become healthy
                if self._wait_for_health_check():
                    logger.info(f"Service started successfully with PID {process.pid}")
                    return {
                        "success": True,
                        "message": f"Service started successfully",
                        "pid": process.pid,
                        "host": host,
                        "port": port,
                        "workers": workers,
                        "health_url": HEALTH_CHECK_URL
                    }
                else:
                    # Service failed to start properly
                    self.stop()
                    return {
                        "success": False,
                        "message": "Service started but failed health check",
                        "log_file": str(self.log_file)
                    }
            else:
                # Start in foreground
                logger.info(f"Starting service in foreground mode")
                process = subprocess.run(cmd, cwd=self.service_dir)
                return {
                    "success": process.returncode == 0,
                    "message": f"Service exited with code {process.returncode}",
                    "return_code": process.returncode
                }
                
        except Exception as e:
            logger.error(f"Failed to start service: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to start service: {str(e)}"
            }
    
    def stop(self, force: bool = False) -> Dict[str, Any]:
        """Stop the AutoScraper service"""
        logger.info(f"Stopping {SERVICE_NAME}...")
        
        pid = self._get_service_pid()
        if not pid:
            return {
                "success": True,
                "message": "Service is not running"
            }
        
        try:
            process = psutil.Process(pid)
            
            if force:
                # Force kill
                process.kill()
                logger.info(f"Force killed service with PID {pid}")
            else:
                # Graceful shutdown
                process.terminate()
                
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=MAX_SHUTDOWN_TIME)
                    logger.info(f"Service with PID {pid} terminated gracefully")
                except psutil.TimeoutExpired:
                    # Force kill if graceful shutdown failed
                    logger.warning(f"Graceful shutdown timed out, force killing PID {pid}")
                    process.kill()
            
            # Clean up PID file
            self._remove_pid_file()
            
            return {
                "success": True,
                "message": f"Service stopped successfully",
                "pid": pid
            }
            
        except psutil.NoSuchProcess:
            # Process already dead
            self._remove_pid_file()
            return {
                "success": True,
                "message": "Service was already stopped"
            }
        except Exception as e:
            logger.error(f"Failed to stop service: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to stop service: {str(e)}"
            }
    
    def restart(self, **kwargs) -> Dict[str, Any]:
        """Restart the AutoScraper service"""
        logger.info(f"Restarting {SERVICE_NAME}...")
        
        # Stop the service
        stop_result = self.stop()
        if not stop_result["success"]:
            return stop_result
        
        # Wait a moment
        time.sleep(2)
        
        # Start the service
        return self.start(**kwargs)
    
    def status(self) -> Dict[str, Any]:
        """Get service status"""
        pid = self._get_service_pid()
        
        if not pid:
            return {
                "running": False,
                "message": "Service is not running"
            }
        
        try:
            process = psutil.Process(pid)
            
            # Get process info
            process_info = {
                "pid": pid,
                "status": process.status(),
                "cpu_percent": process.cpu_percent(),
                "memory_info": process.memory_info()._asdict(),
                "create_time": datetime.fromtimestamp(process.create_time()).isoformat(),
                "cmdline": process.cmdline()
            }
            
            # Check health endpoint
            health_status = "unknown"
            try:
                response = requests.get(HEALTH_CHECK_URL, timeout=5)
                health_status = "healthy" if response.status_code == 200 else "unhealthy"
            except:
                health_status = "unreachable"
            
            return {
                "running": True,
                "health_status": health_status,
                "process_info": process_info,
                "health_url": HEALTH_CHECK_URL
            }
            
        except psutil.NoSuchProcess:
            # Process died, clean up
            self._remove_pid_file()
            return {
                "running": False,
                "message": "Service process not found"
            }
        except Exception as e:
            return {
                "running": False,
                "message": f"Error checking status: {str(e)}"
            }
    
    def logs(self, lines: int = 50) -> Dict[str, Any]:
        """Get service logs"""
        if not self.log_file.exists():
            return {
                "success": False,
                "message": "Log file not found"
            }
        
        try:
            with open(self.log_file, 'r') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            
            return {
                "success": True,
                "lines": recent_lines,
                "total_lines": len(all_lines),
                "log_file": str(self.log_file)
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error reading logs: {str(e)}"
            }

def main():
    """Command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AutoScraper Service Manager")
    parser.add_argument("command", choices=["start", "stop", "restart", "status", "logs"],
                       help="Command to execute")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind to")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind to")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Number of workers")
    parser.add_argument("--foreground", action="store_true", help="Run in foreground")
    parser.add_argument("--force", action="store_true", help="Force stop")
    parser.add_argument("--lines", type=int, default=50, help="Number of log lines to show")
    parser.add_argument("--service-dir", help="Service directory path")
    
    args = parser.parse_args()
    
    manager = ServiceManager(args.service_dir)
    
    if args.command == "start":
        result = manager.start(
            host=args.host,
            port=args.port,
            workers=args.workers,
            background=not args.foreground
        )
    elif args.command == "stop":
        result = manager.stop(force=args.force)
    elif args.command == "restart":
        result = manager.restart(
            host=args.host,
            port=args.port,
            workers=args.workers
        )
    elif args.command == "status":
        result = manager.status()
    elif args.command == "logs":
        result = manager.logs(lines=args.lines)
        if result["success"]:
            print("\n".join(result["lines"]))
            return
    
    # Print result
    print(json.dumps(result, indent=2, default=str))
    
    # Exit with appropriate code
    sys.exit(0 if result.get("success", result.get("running", False)) else 1)

if __name__ == "__main__":
    main()