#!/usr/bin/env python3
"""
API Versioning Support for RemoteHive
Provides version management, deprecation handling, and backward compatibility
"""

from fastapi import Request, HTTPException, status
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime, timedelta
from pydantic import BaseModel
import re


class APIVersion(str, Enum):
    """Supported API versions"""
    V1 = "v1"
    V2 = "v2"


class VersionStatus(str, Enum):
    """Version lifecycle status"""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    RETIRED = "retired"


class VersionInfo(BaseModel):
    """Version information model"""
    version: APIVersion
    status: VersionStatus
    release_date: datetime
    deprecation_date: Optional[datetime] = None
    sunset_date: Optional[datetime] = None
    retirement_date: Optional[datetime] = None
    changelog_url: Optional[str] = None
    migration_guide_url: Optional[str] = None
    breaking_changes: List[str] = []
    new_features: List[str] = []


class VersionRegistry:
    """Registry for managing API versions"""
    
    def __init__(self):
        self.versions: Dict[APIVersion, VersionInfo] = {
            APIVersion.V1: VersionInfo(
                version=APIVersion.V1,
                status=VersionStatus.ACTIVE,
                release_date=datetime(2024, 1, 1),
                changelog_url="/docs/changelog/v1",
                new_features=[
                    "Initial API release",
                    "Authentication and authorization",
                    "Job posting and management",
                    "User management",
                    "Search and filtering"
                ]
            ),
            APIVersion.V2: VersionInfo(
                version=APIVersion.V2,
                status=VersionStatus.ACTIVE,
                release_date=datetime(2024, 6, 1),
                changelog_url="/docs/changelog/v2",
                migration_guide_url="/docs/migration/v1-to-v2",
                breaking_changes=[
                    "Enhanced security validation",
                    "Improved error response format",
                    "Updated pagination structure"
                ],
                new_features=[
                    "Enhanced security features",
                    "Improved API design patterns",
                    "Better error handling",
                    "Advanced search capabilities",
                    "Bulk operations support"
                ]
            )
        }
        self.default_version = APIVersion.V1
        self.latest_version = APIVersion.V2
    
    def get_version_info(self, version: APIVersion) -> VersionInfo:
        """Get version information"""
        return self.versions.get(version)
    
    def is_version_supported(self, version: APIVersion) -> bool:
        """Check if version is supported"""
        version_info = self.get_version_info(version)
        return version_info and version_info.status != VersionStatus.RETIRED
    
    def is_version_deprecated(self, version: APIVersion) -> bool:
        """Check if version is deprecated"""
        version_info = self.get_version_info(version)
        return version_info and version_info.status in [VersionStatus.DEPRECATED, VersionStatus.SUNSET]
    
    def get_active_versions(self) -> List[APIVersion]:
        """Get list of active versions"""
        return [
            version for version, info in self.versions.items()
            if info.status == VersionStatus.ACTIVE
        ]
    
    def get_deprecation_info(self, version: APIVersion) -> Optional[Dict[str, Any]]:
        """Get deprecation information for a version"""
        version_info = self.get_version_info(version)
        if not version_info or not self.is_version_deprecated(version):
            return None
        
        return {
            "version": version,
            "status": version_info.status,
            "deprecation_date": version_info.deprecation_date,
            "sunset_date": version_info.sunset_date,
            "retirement_date": version_info.retirement_date,
            "migration_guide_url": version_info.migration_guide_url,
            "latest_version": self.latest_version
        }


# Global version registry
version_registry = VersionRegistry()


class VersionExtractor:
    """Extract API version from request"""
    
    @staticmethod
    def from_header(request: Request) -> Optional[APIVersion]:
        """Extract version from Accept header"""
        accept_header = request.headers.get("accept", "")
        
        # Look for version in Accept header: application/vnd.remotehive.v1+json
        version_match = re.search(r'application/vnd\.remotehive\.(v\d+)\+json', accept_header)
        if version_match:
            version_str = version_match.group(1)
            try:
                return APIVersion(version_str)
            except ValueError:
                pass
        
        return None
    
    @staticmethod
    def from_custom_header(request: Request) -> Optional[APIVersion]:
        """Extract version from custom header"""
        version_header = request.headers.get("X-API-Version", "")
        if version_header:
            try:
                return APIVersion(version_header.lower())
            except ValueError:
                pass
        return None
    
    @staticmethod
    def from_path(request: Request) -> Optional[APIVersion]:
        """Extract version from URL path"""
        path = request.url.path
        version_match = re.search(r'/api/(v\d+)/', path)
        if version_match:
            version_str = version_match.group(1)
            try:
                return APIVersion(version_str)
            except ValueError:
                pass
        return None
    
    @staticmethod
    def from_query_param(request: Request) -> Optional[APIVersion]:
        """Extract version from query parameter"""
        version_param = request.query_params.get("version", "")
        if version_param:
            try:
                return APIVersion(version_param.lower())
            except ValueError:
                pass
        return None


def get_api_version(request: Request) -> APIVersion:
    """Get API version from request with fallback chain"""
    
    # Try different extraction methods in order of preference
    extractors = [
        VersionExtractor.from_path,
        VersionExtractor.from_custom_header,
        VersionExtractor.from_header,
        VersionExtractor.from_query_param
    ]
    
    for extractor in extractors:
        version = extractor(request)
        if version and version_registry.is_version_supported(version):
            return version
    
    # Return default version if none found or supported
    return version_registry.default_version


def validate_api_version(request: Request) -> APIVersion:
    """Validate and return API version, raise exception if unsupported"""
    version = get_api_version(request)
    
    if not version_registry.is_version_supported(version):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "UNSUPPORTED_API_VERSION",
                "message": f"API version {version} is not supported",
                "supported_versions": version_registry.get_active_versions()
            }
        )
    
    return version


def add_version_headers(response, version: APIVersion, request: Request = None):
    """Add version-related headers to response"""
    version_info = version_registry.get_version_info(version)
    
    # Add current version header
    response.headers["X-API-Version"] = version.value
    response.headers["X-API-Latest-Version"] = version_registry.latest_version.value
    
    # Add deprecation headers if applicable
    if version_registry.is_version_deprecated(version):
        deprecation_info = version_registry.get_deprecation_info(version)
        response.headers["Deprecation"] = "true"
        
        if deprecation_info.get("sunset_date"):
            response.headers["Sunset"] = deprecation_info["sunset_date"].strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        if deprecation_info.get("migration_guide_url"):
            response.headers["Link"] = f'<{deprecation_info["migration_guide_url"]}>; rel="successor-version"'
    
    # Add content type with version
    if "application/json" in response.headers.get("content-type", ""):
        response.headers["Content-Type"] = f"application/vnd.remotehive.{version.value}+json"


class VersionCompatibility:
    """Handle version compatibility and transformations"""
    
    @staticmethod
    def transform_response_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform v1 response format to v2"""
        # Example transformation - wrap in standard response format
        if "status" not in data:
            return {
                "status": "success",
                "data": data,
                "meta": {
                    "version": "v2",
                    "transformed_from": "v1"
                },
                "timestamp": datetime.now().isoformat()
            }
        return data
    
    @staticmethod
    def transform_request_v2_to_v1(data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform v2 request format to v1"""
        # Example transformation - extract data from wrapper
        if "data" in data and isinstance(data["data"], dict):
            return data["data"]
        return data
    
    @staticmethod
    def get_field_mappings(from_version: APIVersion, to_version: APIVersion) -> Dict[str, str]:
        """Get field name mappings between versions"""
        mappings = {
            (APIVersion.V1, APIVersion.V2): {
                "user_id": "id",
                "full_name": "name",
                "phone_number": "phone"
            },
            (APIVersion.V2, APIVersion.V1): {
                "id": "user_id",
                "name": "full_name",
                "phone": "phone_number"
            }
        }
        return mappings.get((from_version, to_version), {})


def create_version_info_response() -> Dict[str, Any]:
    """Create API version information response"""
    return {
        "api_name": "RemoteHive API",
        "current_version": version_registry.latest_version.value,
        "default_version": version_registry.default_version.value,
        "supported_versions": [
            {
                "version": info.version.value,
                "status": info.status.value,
                "release_date": info.release_date.isoformat(),
                "deprecation_date": info.deprecation_date.isoformat() if info.deprecation_date else None,
                "sunset_date": info.sunset_date.isoformat() if info.sunset_date else None,
                "changelog_url": info.changelog_url,
                "migration_guide_url": info.migration_guide_url
            }
            for info in version_registry.versions.values()
            if version_registry.is_version_supported(info.version)
        ],
        "version_selection": {
            "methods": [
                "URL path: /api/v1/endpoint",
                "Header: X-API-Version: v1",
                "Accept header: application/vnd.remotehive.v1+json",
                "Query parameter: ?version=v1"
            ],
            "precedence": "URL path > Custom header > Accept header > Query parameter > Default"
        }
    }