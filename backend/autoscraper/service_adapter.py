#!/usr/bin/env python3
"""
Autoscraper Service Adapter
Proxies requests from the admin panel to the dedicated autoscraper service
"""

from typing import Dict, Any, List, Optional
import httpx
from fastapi import HTTPException, status
from loguru import logger
from datetime import datetime

from backend.core.config import settings

class AutoscraperServiceAdapter:
    """
    Adapter to communicate with the dedicated autoscraper service
    """
    
    def __init__(self):
        # Get autoscraper service URL from settings or use default
        self.base_url = getattr(settings, 'AUTOSCRAPER_SERVICE_URL', 'http://localhost:8001')
        self.api_base = f"{self.base_url}/api/v1/autoscraper"
        self.timeout = 30.0
        self._client = None
        
    @property
    def client(self):
        """Get or create HTTP client"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'RemoteHive-AdminPanel/1.0'
                }
            )
        return self._client
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Don't close the client here as it's reused across requests
        # The client will be recreated if needed via the property
        pass
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to the autoscraper service
        """
        url = f"{self.api_base}{endpoint}"
        
        try:
            logger.debug(f"Making {method} request to {url}")
            
            request_kwargs = {
                'method': method,
                'url': url,
                'params': params or {},
                'headers': headers or {}
            }
            
            if data is not None:
                request_kwargs['json'] = data
            
            response = await self.client.request(**request_kwargs)
            
            # Log response status
            logger.debug(f"Response status: {response.status_code}")
            
            # Handle different response status codes
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 201:
                return response.json()
            elif response.status_code == 204:
                return {'success': True}
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Resource not found in autoscraper service"
                )
            elif response.status_code == 422:
                error_detail = response.json().get('detail', 'Validation error')
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Validation error: {error_detail}"
                )
            elif response.status_code >= 500:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Autoscraper service is currently unavailable"
                )
            else:
                # Try to get error message from response
                try:
                    error_data = response.json()
                    error_message = error_data.get('detail', f'HTTP {response.status_code}')
                except:
                    error_message = f'HTTP {response.status_code}'
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Autoscraper service error: {error_message}"
                )
                
        except httpx.TimeoutException:
            logger.error(f"Timeout when calling autoscraper service: {url}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Autoscraper service request timed out"
            )
        except httpx.ConnectError:
            logger.error(f"Connection error when calling autoscraper service: {url}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cannot connect to autoscraper service. Please ensure it's running."
            )
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling autoscraper service: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal error communicating with autoscraper service: {str(e)}"
            )
    
    # Dashboard methods
    async def get_dashboard(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get dashboard data from autoscraper service"""
        return await self._make_request('GET', '/dashboard', headers=headers)
    
    # Job Board methods
    async def list_job_boards(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """List job boards"""
        params = {'skip': skip, 'limit': limit, 'active_only': active_only}
        return await self._make_request('GET', '/job-boards', params=params)
    
    async def create_job_board(self, job_board_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new job board"""
        return await self._make_request('POST', '/job-boards', data=job_board_data)
    
    async def get_job_board(self, job_board_id: str) -> Dict[str, Any]:
        """Get a specific job board"""
        return await self._make_request('GET', f'/job-boards/{job_board_id}')
    
    async def update_job_board(
        self, 
        job_board_id: str, 
        job_board_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a job board"""
        return await self._make_request('PUT', f'/job-boards/{job_board_id}', data=job_board_data)
    
    async def delete_job_board(self, job_board_id: str) -> Dict[str, Any]:
        """Delete a job board"""
        return await self._make_request('DELETE', f'/job-boards/{job_board_id}')
    
    # Scrape Job methods
    async def list_scrape_jobs(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        job_board_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List scrape jobs"""
        params = {'skip': skip, 'limit': limit}
        if status:
            params['status'] = status
        if job_board_id:
            params['job_board_id'] = job_board_id
        return await self._make_request('GET', '/jobs', params=params)
    
    async def start_scrape_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Start a new scrape job"""
        return await self._make_request('POST', '/jobs/start', data=job_data)
    
    async def pause_scrape_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Pause a scrape job"""
        return await self._make_request('POST', '/jobs/pause', data=job_data)
    
    async def get_scrape_job(self, job_id: str) -> Dict[str, Any]:
        """Get a specific scrape job"""
        return await self._make_request('GET', f'/jobs/{job_id}')
    
    # System methods
    async def hard_reset(self, reset_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform hard reset"""
        return await self._make_request('POST', '/system/hard-reset', data=reset_data)
    
    async def get_health(self) -> Dict[str, Any]:
        """Get health status"""
        return await self._make_request('GET', '/health')
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get system health"""
        return await self._make_request('GET', '/system/health')
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return await self._make_request('GET', '/system/metrics')
    
    # Engine methods
    async def get_engine_state(self) -> Dict[str, Any]:
        """Get engine state"""
        return await self._make_request('GET', '/engine/state')
    
    async def trigger_heartbeat(self) -> Dict[str, Any]:
        """Trigger heartbeat"""
        return await self._make_request('POST', '/engine/heartbeat')
    
    # Logs methods
    async def get_logs(
        self,
        job_id: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> Dict[str, Any]:
        """Get logs"""
        params = {'limit': limit, 'skip': skip}
        if job_id:
            params['job_id'] = job_id
        if level:
            params['level'] = level
        return await self._make_request('GET', '/logs', params=params)
    
    # Settings methods
    async def get_settings(self) -> Dict[str, Any]:
        """Get system settings"""
        return await self._make_request('GET', '/settings')
    
    async def update_settings(self, settings_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update system settings"""
        return await self._make_request('PUT', '/settings', data=settings_data)
    
    async def update_system_settings(self, settings_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update system settings (alias for update_settings)"""
        return await self.update_settings(settings_data)
    
    async def reset_settings(self) -> Dict[str, Any]:
        """Reset system settings to defaults"""
        return await self._make_request('POST', '/settings/reset')
    
    async def test_settings(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test system settings"""
        return await self._make_request('POST', '/settings/test', data=test_data)
    
    async def health_check(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get health check status (alias for get_health)"""
        return await self._make_request('GET', '/health', headers=headers)
    
    async def get_live_logs(self, **kwargs) -> Dict[str, Any]:
        """Get live logs (alias for get_logs)"""
        return await self.get_logs(**kwargs)
    
    # Runs methods
    async def list_scrape_runs(
        self,
        skip: int = 0,
        limit: int = 100,
        job_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List scrape runs"""
        params = {'skip': skip, 'limit': limit}
        if job_id:
            params['job_id'] = job_id
        return await self._make_request('GET', '/runs', params=params)
    
    async def get_scrape_run(self, run_id: str) -> Dict[str, Any]:
        """Get a specific scrape run"""
        return await self._make_request('GET', f'/runs/{run_id}')


# Global adapter instance
_adapter_instance = None

def get_autoscraper_adapter() -> AutoscraperServiceAdapter:
    """Get the global autoscraper service adapter instance"""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = AutoscraperServiceAdapter()
    return _adapter_instance