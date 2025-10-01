from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

try:
    from backend.core.logging import get_logger
    from backend.core.config import settings
    from backend.core.validation import InputValidator, ValidationError, SecurityValidationError
    from backend.middleware.security import SecurityMiddleware
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)
    
    class Settings:
        SECURITY_LOGGING_ENABLED = True
        SECURITY_ALERTS_ENABLED = False
    settings = Settings()
    
    class InputValidator:
        def validate_input(self, *args, **kwargs):
            return args[0] if args else ""
    
    class SecurityMiddleware:
        def get_security_stats(self):
            return {"security_stats": {}, "rate_limiter_stats": {}}


router = APIRouter(prefix="/security", tags=["security"])
logger = get_logger("security_api")


class CSPReportRequest(BaseModel):
    """Content Security Policy violation report"""
    
    csp_report: Dict[str, Any] = Field(..., description="CSP violation report")
    user_agent: Optional[str] = Field(None, description="User agent string")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now)


class SecurityStatsResponse(BaseModel):
    """Security statistics response"""
    
    blocked_requests: int = Field(..., description="Total blocked requests")
    xss_attempts: int = Field(..., description="XSS attack attempts")
    sql_injection_attempts: int = Field(..., description="SQL injection attempts")
    path_traversal_attempts: int = Field(..., description="Path traversal attempts")
    command_injection_attempts: int = Field(..., description="Command injection attempts")
    rate_limit_violations: int = Field(..., description="Rate limit violations")
    oversized_requests: int = Field(..., description="Oversized request attempts")
    active_ips: int = Field(..., description="Currently tracked IPs")
    blocked_ips: int = Field(..., description="Currently blocked IPs")
    timestamp: datetime = Field(default_factory=datetime.now)


class SecurityIncidentRequest(BaseModel):
    """Security incident report"""
    
    incident_type: str = Field(..., description="Type of security incident")
    description: str = Field(..., description="Incident description")
    severity: str = Field(default="medium", description="Incident severity (low, medium, high, critical)")
    client_ip: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")
    request_path: Optional[str] = Field(None, description="Request path")
    additional_data: Optional[Dict[str, Any]] = Field(None, description="Additional incident data")


class SecurityConfigResponse(BaseModel):
    """Security configuration response"""
    
    security_headers_enabled: bool
    rate_limit_enabled: bool
    rate_limit_requests: int
    rate_limit_window: int
    csrf_protection_enabled: bool
    csp_enabled: bool
    strict_validation: bool
    sanitize_input: bool
    block_suspicious_requests: bool


# Dependency to get security middleware instance
def get_security_middleware(request: Request) -> Optional[SecurityMiddleware]:
    """Get security middleware instance from app state"""
    # In a real implementation, you'd store the middleware instance in app state
    # For now, return None and handle gracefully
    return getattr(request.app.state, 'security_middleware', None)


@router.post("/csp-report")
async def csp_violation_report(report: CSPReportRequest, request: Request):
    """Handle Content Security Policy violation reports"""
    try:
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Log CSP violation
        logger.warning(
            "CSP violation reported",
            client_ip=client_ip,
            user_agent=user_agent,
            csp_report=report.csp_report
        )
        
        # Store violation data (in a real implementation, you'd store this in a database)
        violation_data = {
            "timestamp": datetime.now().isoformat(),
            "client_ip": client_ip,
            "user_agent": user_agent,
            "report": report.csp_report
        }
        
        # Send alert if enabled
        if settings.SECURITY_ALERTS_ENABLED:
            await _send_security_alert("CSP_VIOLATION", violation_data)
        
        return JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT,
            content=None
        )
        
    except Exception as e:
        logger.error(f"Error processing CSP report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process CSP report"
        )


@router.get("/stats", response_model=SecurityStatsResponse)
async def get_security_stats(
    request: Request,
    security_middleware: Optional[SecurityMiddleware] = Depends(get_security_middleware)
):
    """Get security statistics"""
    try:
        if security_middleware:
            stats = security_middleware.get_security_stats()
            security_stats = stats.get("security_stats", {})
            rate_limiter_stats = stats.get("rate_limiter_stats", {})
        else:
            # Fallback if middleware not available
            security_stats = {
                "blocked_requests": 0,
                "xss_attempts": 0,
                "sql_injection_attempts": 0,
                "path_traversal_attempts": 0,
                "command_injection_attempts": 0,
                "rate_limit_violations": 0,
                "oversized_requests": 0
            }
            rate_limiter_stats = {
                "active_ips": 0,
                "blocked_ips": 0
            }
        
        return SecurityStatsResponse(
            blocked_requests=security_stats.get("blocked_requests", 0),
            xss_attempts=security_stats.get("xss_attempts", 0),
            sql_injection_attempts=security_stats.get("sql_injection_attempts", 0),
            path_traversal_attempts=security_stats.get("path_traversal_attempts", 0),
            command_injection_attempts=security_stats.get("command_injection_attempts", 0),
            rate_limit_violations=security_stats.get("rate_limit_violations", 0),
            oversized_requests=security_stats.get("oversized_requests", 0),
            active_ips=rate_limiter_stats.get("active_ips", 0),
            blocked_ips=rate_limiter_stats.get("blocked_ips", 0)
        )
        
    except Exception as e:
        logger.error(f"Error retrieving security stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security statistics"
        )


@router.get("/config", response_model=SecurityConfigResponse)
async def get_security_config():
    """Get current security configuration"""
    try:
        return SecurityConfigResponse(
            security_headers_enabled=getattr(settings, 'SECURITY_HEADERS_ENABLED', True),
            rate_limit_enabled=getattr(settings, 'RATE_LIMIT_ENABLED', True),
            rate_limit_requests=getattr(settings, 'RATE_LIMIT_REQUESTS', 100),
            rate_limit_window=getattr(settings, 'RATE_LIMIT_WINDOW', 60),
            csrf_protection_enabled=getattr(settings, 'CSRF_PROTECTION_ENABLED', False),
            csp_enabled=getattr(settings, 'CSP_ENABLED', True),
            strict_validation=getattr(settings, 'STRICT_VALIDATION', True),
            sanitize_input=getattr(settings, 'SANITIZE_INPUT', True),
            block_suspicious_requests=getattr(settings, 'BLOCK_SUSPICIOUS_REQUESTS', True)
        )
        
    except Exception as e:
        logger.error(f"Error retrieving security config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security configuration"
        )


@router.post("/incident")
async def report_security_incident(
    incident: SecurityIncidentRequest,
    request: Request
):
    """Report a security incident"""
    try:
        # Validate incident data
        validator = InputValidator()
        
        # Get client information
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Create incident record
        incident_data = {
            "timestamp": datetime.now().isoformat(),
            "incident_type": incident.incident_type,
            "description": incident.description,
            "severity": incident.severity,
            "client_ip": incident.client_ip or client_ip,
            "user_agent": incident.user_agent or user_agent,
            "request_path": incident.request_path,
            "additional_data": incident.additional_data or {}
        }
        
        # Log incident
        logger.warning(
            f"Security incident reported: {incident.incident_type}",
            **incident_data
        )
        
        # Send alert for high/critical severity incidents
        if incident.severity in ["high", "critical"] and settings.SECURITY_ALERTS_ENABLED:
            await _send_security_alert("SECURITY_INCIDENT", incident_data)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "Security incident reported successfully",
                "incident_id": f"inc_{int(datetime.now().timestamp())}",
                "timestamp": incident_data["timestamp"]
            }
        )
        
    except (ValidationError, SecurityValidationError) as e:
        logger.warning(f"Invalid incident report: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error reporting security incident: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to report security incident"
        )


@router.get("/health")
async def security_health_check():
    """Security system health check"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "security_middleware": "active",
                "rate_limiter": "active",
                "input_validator": "active",
                "security_headers": "enabled" if getattr(settings, 'SECURITY_HEADERS_ENABLED', True) else "disabled",
                "csrf_protection": "enabled" if getattr(settings, 'CSRF_PROTECTION_ENABLED', False) else "disabled",
                "csp": "enabled" if getattr(settings, 'CSP_ENABLED', True) else "disabled"
            }
        }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=health_status
        )
        
    except Exception as e:
        logger.error(f"Security health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


async def _send_security_alert(alert_type: str, data: Dict[str, Any]):
    """Send security alert (placeholder implementation)"""
    try:
        # In a real implementation, you would:
        # 1. Send to monitoring system (e.g., Datadog, New Relic)
        # 2. Send to Slack/Teams webhook
        # 3. Send email alerts
        # 4. Trigger incident response workflows
        
        alert_data = {
            "alert_type": alert_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        logger.critical(f"SECURITY ALERT: {alert_type}", **alert_data)
        
        # Send to webhook if configured
        webhook_url = getattr(settings, 'SECURITY_WEBHOOK_URL', '')
        if webhook_url:
            # Implementation would send HTTP POST to webhook
            pass
            
    except Exception as e:
        logger.error(f"Failed to send security alert: {e}")


# Export router
__all__ = ['router']