"""Minimal test suite for basic API functionality."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app


class TestBasicAPI:
    """Test basic API functionality that actually exists."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_app_startup(self, client):
        """Test that the app starts up correctly."""
        assert client is not None
        assert app is not None
    
    def test_docs_endpoint(self, client):
        """Test API documentation endpoint."""
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_openapi_endpoint(self, client):
        """Test OpenAPI schema endpoint."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "openapi" in response.json()
    
    def test_redoc_endpoint(self, client):
        """Test ReDoc endpoint."""
        response = client.get("/redoc")
        assert response.status_code == 200
    
    def test_404_handling(self, client):
        """Test 404 error handling."""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404





if __name__ == "__main__":
    pytest.main([__file__, "-v"])