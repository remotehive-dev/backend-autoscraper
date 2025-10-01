# Import the main API router directly from api.py
from backend.api.v1.api import api_router

# Export the main router
__all__ = ['api_router']