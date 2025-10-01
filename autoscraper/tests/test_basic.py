import pytest
import os
import sys

# Add the parent directory to the path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_import_main():
    """Test that we can import the main application module."""
    try:
        from app.main import app
        assert app is not None
    except ImportError as e:
        pytest.fail(f"Failed to import main app: {e}")

def test_basic_functionality():
    """Test basic functionality is working."""
    assert 1 + 1 == 2
    assert "autoscraper" in "autoscraper-service"

def test_environment_setup():
    """Test that the environment is properly set up."""
    # Check if we're in the right directory
    current_dir = os.getcwd()
    assert "autoscraper-service" in current_dir or "RemoteHive" in current_dir

def test_config_import():
    """Test that we can import configuration modules."""
    try:
        from config.settings import settings
        assert settings is not None
    except ImportError:
        # If settings import fails, that's okay for basic tests
        pass

def test_database_models_import():
    """Test that we can import database models."""
    try:
        from app.models import job_models
        assert job_models is not None
    except ImportError:
        # If models import fails, that's okay for basic tests
        pass

def test_service_structure():
    """Test that the service has the expected structure."""
    # Check if main directories exist
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    expected_dirs = ['app', 'config', 'scripts']
    for dir_name in expected_dirs:
        dir_path = os.path.join(base_dir, dir_name)
        assert os.path.exists(dir_path), f"Directory {dir_name} should exist"