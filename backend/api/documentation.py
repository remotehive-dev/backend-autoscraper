#!/usr/bin/env python3
"""
API Documentation and OpenAPI Schema Enhancement for RemoteHive
Provides comprehensive API documentation, schema validation, and interactive docs
"""

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
import json

from backend.core.config import settings
from backend.api.versioning import APIVersion, VersionInfo, VersionRegistry


class APIDocumentation:
    """Enhanced API documentation generator"""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.version_registry = VersionRegistry()
    
    def setup_documentation(self):
        """Setup enhanced API documentation"""
        # Custom OpenAPI schema
        self.app.openapi = self.custom_openapi
        
        # Custom documentation routes
        self.setup_custom_docs_routes()
        
        # Add API info and metadata
        self.enhance_api_metadata()
    
    def custom_openapi(self) -> Dict[str, Any]:
        """Generate custom OpenAPI schema"""
        if self.app.openapi_schema:
            return self.app.openapi_schema
        
        # Get base OpenAPI schema
        openapi_schema = get_openapi(
            title="RemoteHive API",
            version=self.get_current_version(),
            description=self.get_api_description(),
            routes=self.app.routes,
            servers=self.get_servers_config()
        )
        
        # Enhance schema with custom information
        self.enhance_openapi_schema(openapi_schema)
        
        self.app.openapi_schema = openapi_schema
        return self.app.openapi_schema
    
    def get_current_version(self) -> str:
        """Get current API version"""
        return "2.0.0"  # Updated version with enhancements
    
    def get_api_description(self) -> str:
        """Get comprehensive API description"""
        return """
        # RemoteHive API Documentation
        
        Welcome to the RemoteHive API - a comprehensive platform for remote job management and recruitment.
        
        ## Features
        
        - **Authentication & Authorization**: Secure JWT-based authentication with role-based access control
        - **Job Management**: Complete job posting, application, and workflow management
        - **User Management**: Comprehensive user profiles for job seekers and employers
        - **Company Management**: Company profiles and employer management
        - **Advanced Search**: Powerful search and filtering capabilities
        - **Real-time Notifications**: WebSocket-based real-time updates
        - **File Management**: Secure file upload and management
        - **Analytics & Reporting**: Comprehensive analytics and reporting features
        - **Web Scraping**: Automated job scraping from multiple sources
        - **ML Intelligence**: AI-powered job matching and recommendations
        
        ## API Versions
        
        - **v1**: Legacy API (deprecated, maintained for compatibility)
        - **v2**: Current API with enhanced features and security
        
        ## Authentication
        
        The API uses JWT (JSON Web Tokens) for authentication. Include the token in the Authorization header:
        
        ```
        Authorization: Bearer <your-jwt-token>
        ```
        
        ## Rate Limiting
        
        API requests are rate-limited to ensure fair usage:
        - **Standard**: 100 requests per minute
        - **Premium**: 1000 requests per minute
        - **Enterprise**: Custom limits
        
        ## Error Handling
        
        The API uses standard HTTP status codes and returns detailed error information:
        
        ```json
        {
            "error_code": "VALIDATION_ERROR",
            "message": "Invalid input data",
            "details": {
                "field_errors": [
                    {
                        "field": "email",
                        "message": "Invalid email format"
                    }
                ]
            },
            "timestamp": "2024-01-20T10:30:00Z"
        }
        ```
        
        ## Security
        
        - All endpoints use HTTPS in production
        - Input validation and sanitization
        - SQL injection protection
        - XSS protection
        - CSRF protection
        - Rate limiting and DDoS protection
        
        ## Support
        
        For API support, please contact:
        - Email: api-support@remotehive.com
        - Documentation: https://docs.remotehive.com
        - Status Page: https://status.remotehive.com
        """
    
    def get_servers_config(self) -> List[Dict[str, str]]:
        """Get servers configuration for different environments"""
        servers = []
        
        # Production server
        if hasattr(settings, 'PRODUCTION_URL'):
            servers.append({
                "url": settings.PRODUCTION_URL,
                "description": "Production server"
            })
        
        # Staging server
        if hasattr(settings, 'STAGING_URL'):
            servers.append({
                "url": settings.STAGING_URL,
                "description": "Staging server"
            })
        
        # Development server
        servers.append({
            "url": "http://localhost:8000",
            "description": "Development server"
        })
        
        return servers
    
    def enhance_openapi_schema(self, schema: Dict[str, Any]):
        """Enhance OpenAPI schema with additional information"""
        # Add contact information
        schema["info"]["contact"] = {
            "name": "RemoteHive API Support",
            "email": "api-support@remotehive.com",
            "url": "https://docs.remotehive.com"
        }
        
        # Add license information
        schema["info"]["license"] = {
            "name": "Proprietary",
            "url": "https://remotehive.com/license"
        }
        
        # Add external documentation
        schema["externalDocs"] = {
            "description": "Complete API Documentation",
            "url": "https://docs.remotehive.com"
        }
        
        # Add security schemes
        schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT token obtained from /auth/login endpoint"
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for service-to-service authentication"
            }
        }
        
        # Add global security requirement
        schema["security"] = [
            {"BearerAuth": []},
            {"ApiKeyAuth": []}
        ]
        
        # Add tags for better organization
        schema["tags"] = [
            {
                "name": "Authentication",
                "description": "User authentication and authorization endpoints"
            },
            {
                "name": "Users",
                "description": "User management and profile endpoints"
            },
            {
                "name": "Jobs",
                "description": "Job posting and management endpoints"
            },
            {
                "name": "Companies",
                "description": "Company and employer management endpoints"
            },
            {
                "name": "Applications",
                "description": "Job application management endpoints"
            },
            {
                "name": "Search",
                "description": "Search and filtering endpoints"
            },
            {
                "name": "Notifications",
                "description": "Notification management endpoints"
            },
            {
                "name": "Analytics",
                "description": "Analytics and reporting endpoints"
            },
            {
                "name": "Admin",
                "description": "Administrative endpoints (admin access required)"
            },
            {
                "name": "Scraping",
                "description": "Web scraping and data collection endpoints"
            },
            {
                "name": "ML Intelligence",
                "description": "Machine learning and AI-powered endpoints"
            }
        ]
        
        # Add custom extensions
        schema["x-api-version"] = self.get_current_version()
        schema["x-api-status"] = "stable"
        schema["x-rate-limit"] = {
            "requests": 100,
            "window": "1 minute"
        }
        
        # Enhance path operations
        self.enhance_path_operations(schema)
    
    def enhance_path_operations(self, schema: Dict[str, Any]):
        """Enhance individual path operations with additional metadata"""
        if "paths" not in schema:
            return
        
        for path, path_item in schema["paths"].items():
            for method, operation in path_item.items():
                if method.upper() in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
                    # Add operation metadata
                    if "tags" not in operation:
                        operation["tags"] = [self.infer_tag_from_path(path)]
                    
                    # Add response examples
                    self.add_response_examples(operation)
                    
                    # Add security requirements based on path
                    if not path.startswith("/auth/") and not path.startswith("/health"):
                        operation["security"] = [{"BearerAuth": []}]
    
    def infer_tag_from_path(self, path: str) -> str:
        """Infer appropriate tag from API path"""
        path_segments = path.strip("/").split("/")
        
        if "auth" in path_segments:
            return "Authentication"
        elif "users" in path_segments:
            return "Users"
        elif "jobs" in path_segments:
            return "Jobs"
        elif "companies" in path_segments or "employers" in path_segments:
            return "Companies"
        elif "applications" in path_segments:
            return "Applications"
        elif "search" in path_segments:
            return "Search"
        elif "notifications" in path_segments:
            return "Notifications"
        elif "analytics" in path_segments:
            return "Analytics"
        elif "admin" in path_segments:
            return "Admin"
        elif "scraper" in path_segments or "scraping" in path_segments:
            return "Scraping"
        elif "ml" in path_segments or "intelligence" in path_segments:
            return "ML Intelligence"
        else:
            return "General"
    
    def add_response_examples(self, operation: Dict[str, Any]):
        """Add response examples to operation"""
        if "responses" not in operation:
            return
        
        for status_code, response in operation["responses"].items():
            if status_code == "200" and "content" in response:
                # Add success example
                for content_type, content_info in response["content"].items():
                    if "examples" not in content_info:
                        content_info["examples"] = {
                            "success": {
                                "summary": "Successful response",
                                "value": self.generate_success_example(operation)
                            }
                        }
            
            elif status_code.startswith("4") or status_code.startswith("5"):
                # Add error example
                if "content" in response:
                    for content_type, content_info in response["content"].items():
                        if "examples" not in content_info:
                            content_info["examples"] = {
                                "error": {
                                    "summary": "Error response",
                                    "value": self.generate_error_example(status_code)
                                }
                            }
    
    def generate_success_example(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Generate success response example"""
        return {
            "success": True,
            "data": {},
            "message": "Operation completed successfully",
            "timestamp": datetime.now().isoformat()
        }
    
    def generate_error_example(self, status_code: str) -> Dict[str, Any]:
        """Generate error response example"""
        error_messages = {
            "400": "Bad Request - Invalid input data",
            "401": "Unauthorized - Authentication required",
            "403": "Forbidden - Insufficient permissions",
            "404": "Not Found - Resource not found",
            "422": "Validation Error - Input validation failed",
            "429": "Too Many Requests - Rate limit exceeded",
            "500": "Internal Server Error - Server error occurred"
        }
        
        return {
            "error_code": f"HTTP_{status_code}",
            "message": error_messages.get(status_code, "An error occurred"),
            "details": {},
            "timestamp": datetime.now().isoformat()
        }
    
    def setup_custom_docs_routes(self):
        """Setup custom documentation routes"""
        
        @self.app.get("/docs", include_in_schema=False)
        async def custom_swagger_ui_html(request: Request):
            """Custom Swagger UI with enhanced styling"""
            return get_swagger_ui_html(
                openapi_url="/openapi.json",
                title="RemoteHive API Documentation",
                swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
                swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
                swagger_ui_parameters={
                    "deepLinking": True,
                    "displayRequestDuration": True,
                    "docExpansion": "none",
                    "operationsSorter": "alpha",
                    "filter": True,
                    "showExtensions": True,
                    "showCommonExtensions": True,
                    "tryItOutEnabled": True
                }
            )
        
        @self.app.get("/redoc", include_in_schema=False)
        async def redoc_html(request: Request):
            """ReDoc documentation"""
            return get_redoc_html(
                openapi_url="/openapi.json",
                title="RemoteHive API Documentation",
                redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.0.0/bundles/redoc.standalone.js"
            )
        
        @self.app.get("/api-info", include_in_schema=False)
        async def api_info():
            """API information endpoint"""
            return {
                "name": "RemoteHive API",
                "version": self.get_current_version(),
                "description": "Remote job management and recruitment platform API",
                "documentation": {
                    "swagger": "/docs",
                    "redoc": "/redoc",
                    "openapi": "/openapi.json"
                },
                "support": {
                    "email": "api-support@remotehive.com",
                    "docs": "https://docs.remotehive.com",
                    "status": "https://status.remotehive.com"
                },
                "rate_limits": {
                    "standard": "100 requests/minute",
                    "premium": "1000 requests/minute",
                    "enterprise": "Custom limits"
                },
                "versions": self.version_registry.get_all_versions(),
                "timestamp": datetime.now().isoformat()
            }
    
    def enhance_api_metadata(self):
        """Enhance API metadata and configuration"""
        # Update app metadata
        self.app.title = "RemoteHive API"
        self.app.description = self.get_api_description()
        self.app.version = self.get_current_version()
        
        # Add custom middleware for documentation
        self.add_documentation_middleware()
    
    def add_documentation_middleware(self):
        """Add middleware for documentation enhancement"""
        
        @self.app.middleware("http")
        async def add_api_headers(request: Request, call_next):
            """Add API information headers"""
            response = await call_next(request)
            
            # Add API version header
            response.headers["X-API-Version"] = self.get_current_version()
            response.headers["X-API-Name"] = "RemoteHive API"
            
            # Add documentation links
            if request.url.path == "/":
                response.headers["X-API-Docs"] = "/docs"
                response.headers["X-API-Schema"] = "/openapi.json"
            
            return response


class SchemaValidator:
    """Enhanced schema validation utilities"""
    
    @staticmethod
    def validate_openapi_schema(schema: Dict[str, Any]) -> List[str]:
        """Validate OpenAPI schema for completeness and correctness"""
        issues = []
        
        # Check required fields
        required_fields = ["openapi", "info", "paths"]
        for field in required_fields:
            if field not in schema:
                issues.append(f"Missing required field: {field}")
        
        # Check info section
        if "info" in schema:
            info_required = ["title", "version"]
            for field in info_required:
                if field not in schema["info"]:
                    issues.append(f"Missing required info field: {field}")
        
        # Check paths
        if "paths" in schema:
            for path, path_item in schema["paths"].items():
                for method, operation in path_item.items():
                    if method.upper() in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
                        # Check operation has summary or description
                        if "summary" not in operation and "description" not in operation:
                            issues.append(f"Operation {method.upper()} {path} missing summary/description")
                        
                        # Check responses
                        if "responses" not in operation:
                            issues.append(f"Operation {method.upper()} {path} missing responses")
        
        return issues
    
    @staticmethod
    def generate_schema_report(schema: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive schema report"""
        report = {
            "schema_version": schema.get("openapi", "unknown"),
            "api_version": schema.get("info", {}).get("version", "unknown"),
            "total_paths": len(schema.get("paths", {})),
            "total_operations": 0,
            "operations_by_method": {},
            "tags": [],
            "security_schemes": [],
            "components": {
                "schemas": 0,
                "responses": 0,
                "parameters": 0,
                "examples": 0
            },
            "validation_issues": SchemaValidator.validate_openapi_schema(schema)
        }
        
        # Count operations
        if "paths" in schema:
            for path_item in schema["paths"].values():
                for method in path_item:
                    if method.upper() in ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]:
                        report["total_operations"] += 1
                        report["operations_by_method"][method.upper()] = report["operations_by_method"].get(method.upper(), 0) + 1
        
        # Extract tags
        if "tags" in schema:
            report["tags"] = [tag["name"] for tag in schema["tags"]]
        
        # Extract security schemes
        if "components" in schema and "securitySchemes" in schema["components"]:
            report["security_schemes"] = list(schema["components"]["securitySchemes"].keys())
        
        # Count components
        if "components" in schema:
            components = schema["components"]
            for component_type in ["schemas", "responses", "parameters", "examples"]:
                if component_type in components:
                    report["components"][component_type] = len(components[component_type])
        
        return report


def setup_api_documentation(app: FastAPI) -> APIDocumentation:
    """Setup comprehensive API documentation"""
    doc_manager = APIDocumentation(app)
    doc_manager.setup_documentation()
    return doc_manager