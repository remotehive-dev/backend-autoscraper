#!/usr/bin/env python3
"""
Configuration Loader for AutoScraper Service

This module provides utilities for loading and validating environment-specific
configurations for the AutoScraper service.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Add the parent directory to the path to import settings
sys.path.append(str(Path(__file__).parent.parent))

from config.settings import get_settings, AutoscraperSettings


class ConfigLoader:
    """Configuration loader and validator for AutoScraper service."""
    
    def __init__(self, environment: Optional[str] = None):
        """Initialize the configuration loader.
        
        Args:
            environment: Target environment (development, staging, production)
        """
        self.environment = environment or os.getenv('ENVIRONMENT', 'development')
        self.base_dir = Path(__file__).parent.parent
        self.env_file = None
        
    def load_environment_config(self) -> bool:
        """Load environment-specific configuration file.
        
        Returns:
            bool: True if configuration loaded successfully, False otherwise
        """
        env_files = [
            self.base_dir / f".env.{self.environment}",
            self.base_dir / ".env",
            self.base_dir / ".env.example"
        ]
        
        for env_file in env_files:
            if env_file.exists():
                print(f"Loading configuration from: {env_file}")
                load_dotenv(env_file, override=True)
                self.env_file = env_file
                return True
                
        print(f"Warning: No environment file found for environment '{self.environment}'")
        return False
        
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate the loaded configuration.
        
        Returns:
            Dict containing validation results and settings
        """
        try:
            settings = get_settings()
            validation_result = {
                'valid': True,
                'settings': settings,
                'environment': self.environment,
                'env_file': str(self.env_file) if self.env_file else None,
                'errors': [],
                'warnings': []
            }
            
            # Validate critical settings
            self._validate_database_config(settings, validation_result)
            self._validate_security_config(settings, validation_result)
            self._validate_service_config(settings, validation_result)
            
            return validation_result
            
        except Exception as e:
            return {
                'valid': False,
                'settings': None,
                'environment': self.environment,
                'env_file': str(self.env_file) if self.env_file else None,
                'errors': [f"Configuration validation failed: {str(e)}"],
                'warnings': []
            }
            
    def _validate_database_config(self, settings: AutoscraperSettings, result: Dict[str, Any]):
        """Validate database configuration."""
        if not settings.DATABASE_URL:
            result['errors'].append("DATABASE_URL is not configured")
            result['valid'] = False
            
        if settings.DATABASE_URL and settings.DATABASE_URL.startswith('sqlite'):
            if self.environment == 'production':
                result['warnings'].append("SQLite is not recommended for production")
                
    def _validate_security_config(self, settings: AutoscraperSettings, result: Dict[str, Any]):
        """Validate security configuration."""
        if not settings.JWT_SECRET_KEY or settings.JWT_SECRET_KEY == 'your-super-secret-jwt-key-change-in-production':
            if self.environment == 'production':
                result['errors'].append("JWT_SECRET_KEY must be set to a secure value in production")
                result['valid'] = False
            else:
                result['warnings'].append("JWT_SECRET_KEY should be changed from default value")
                
        if self.environment == 'production':
            if settings.DEBUG:
                result['errors'].append("DEBUG should be disabled in production")
                result['valid'] = False
                
    def _validate_service_config(self, settings: AutoscraperSettings, result: Dict[str, Any]):
        """Validate service configuration."""
        if not settings.SERVICE_NAME:
            result['warnings'].append("SERVICE_NAME is not configured")
            
        if settings.PORT < 1024 and os.getuid() != 0:
            result['warnings'].append(f"Port {settings.PORT} may require root privileges")
            
    def print_configuration_summary(self, validation_result: Dict[str, Any]):
        """Print a summary of the configuration."""
        print("\n" + "="*60)
        print(f"AutoScraper Configuration Summary")
        print("="*60)
        print(f"Environment: {validation_result['environment']}")
        print(f"Config File: {validation_result['env_file'] or 'None'}")
        print(f"Valid: {'✓' if validation_result['valid'] else '✗'}")
        
        if validation_result['settings']:
            settings = validation_result['settings']
            print(f"\nService Configuration:")
            print(f"  Name: {settings.SERVICE_NAME}")
            print(f"  Environment: {settings.ENVIRONMENT}")
            print(f"  Host: {settings.HOST}")
            print(f"  Port: {settings.PORT}")
            print(f"  Debug: {settings.DEBUG}")
            
            print(f"\nDatabase:")
            db_type = 'SQLite' if settings.DATABASE_URL.startswith('sqlite') else 'PostgreSQL'
            print(f"  Type: {db_type}")
            print(f"  URL: {settings.DATABASE_URL[:50]}..." if len(settings.DATABASE_URL) > 50 else settings.DATABASE_URL)
            
        if validation_result['errors']:
            print(f"\nErrors ({len(validation_result['errors'])}):")
            for error in validation_result['errors']:
                print(f"  ✗ {error}")
                
        if validation_result['warnings']:
            print(f"\nWarnings ({len(validation_result['warnings'])}):")
            for warning in validation_result['warnings']:
                print(f"  ⚠ {warning}")
                
        print("="*60)
        

def main():
    """Main function for running configuration validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description='AutoScraper Configuration Loader')
    parser.add_argument('--environment', '-e', 
                       choices=['development', 'staging', 'production'],
                       help='Target environment')
    parser.add_argument('--validate-only', '-v', action='store_true',
                       help='Only validate configuration, do not start service')
    
    args = parser.parse_args()
    
    # Load configuration
    loader = ConfigLoader(environment=args.environment)
    
    print(f"Loading configuration for environment: {loader.environment}")
    
    # Load environment file
    if not loader.load_environment_config():
        print("Failed to load environment configuration")
        sys.exit(1)
        
    # Validate configuration
    validation_result = loader.validate_configuration()
    
    # Print summary
    loader.print_configuration_summary(validation_result)
    
    # Exit with appropriate code
    if not validation_result['valid']:
        print("\nConfiguration validation failed!")
        sys.exit(1)
    else:
        print("\nConfiguration validation successful!")
        sys.exit(0)
        

if __name__ == '__main__':
    main()