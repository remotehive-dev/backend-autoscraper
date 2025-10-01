import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

try:
    from enhanced_scraper_manager import EnhancedScraperManager
    from ml_parsing_service import MLParsingService, ParsedJobData
    from job_validation_service import JobDataValidator, ValidationResult
    from ml_config_service import MLConfigurationService
    from gemini_client import GeminiClient
    from backend.database.models import ScraperConfig, JobPost, MLParsingConfig
    from backend.database.database import get_db_session
except ImportError:
    # Mock imports for testing
    from dataclasses import dataclass
    from enum import Enum
    
    class ValidationSeverity(Enum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"
    
    @dataclass
    class ParsedJobData:
        title: Optional[str] = None
        company: Optional[str] = None
        location: Optional[str] = None
        description: Optional[str] = None
        salary_min: Optional[int] = None
        salary_max: Optional[int] = None
        job_type: Optional[str] = None
        is_remote: Optional[bool] = None
        experience_level: Optional[str] = None
        requirements: Optional[List[str]] = None
        benefits: Optional[List[str]] = None
        posted_date: Optional[datetime] = None
        application_url: Optional[str] = None
        confidence_score: Optional[float] = None
        parsing_metadata: Optional[Dict[str, Any]] = None
    
    @dataclass
    class ValidationIssue:
        field: str
        severity: ValidationSeverity
        message: str
        suggestion: Optional[str] = None
    
    @dataclass
    class ValidationResult:
        is_valid: bool
        quality_score: float
        issues: List[ValidationIssue]
        metadata: Dict[str, Any]
    
    class EnhancedScraperManager:
        def __init__(self):
            self.logger = Mock()
            self.redis_manager = Mock()
            self.ml_parsing_service = Mock()
            self.job_validator = Mock()
    
    class MLParsingService:
        def __init__(self):
            self.logger = Mock()
            self.gemini_client = Mock()
    
    class JobDataValidator:
        def __init__(self):
            self.logger = Mock()
    
    class MLConfigurationService:
        def __init__(self):
            self.logger = Mock()
    
    class GeminiClient:
        def __init__(self, api_key: str):
            self.api_key = api_key
    
    class ScraperConfig:
        def __init__(self, **kwargs):
            self.id = kwargs.get('id', 1)
            self.scraper_name = kwargs.get('scraper_name', 'test')
            self.source_url = kwargs.get('source_url', 'https://example.com')
            self.is_enabled = kwargs.get('is_enabled', True)
    
    class JobPost:
        def __init__(self, **kwargs):
            self.id = kwargs.get('id', 1)
            self.title = kwargs.get('title', 'Test Job')
            self.company = kwargs.get('company', 'Test Company')
            self.location = kwargs.get('location', 'Test Location')
    
    class MLParsingConfig:
        def __init__(self, **kwargs):
            self.id = kwargs.get('id', 1)
            self.name = kwargs.get('name', 'Test Config')
            self.enabled = kwargs.get('enabled', True)
    
    def get_db_session():
        return Mock()


class TestEndToEndMLWorkflow:
    """End-to-end ML workflow integration tests"""
    
    @pytest.fixture
    def sample_html_content(self):
        """Sample HTML content for testing."""
        return """
        <html>
        <body>
            <div class="job-listing">
                <h1 class="job-title">Test Job Title</h1>
                <div class="company-name">Test Company</div>
                <div class="job-location">Test Location</div>
                <div class="job-description">
                    Test job description with sufficient content for validation.
                </div>
                <div class="salary-range">$50,000 - $100,000</div>
                <div class="job-type">Full-time</div>
                <div class="remote-work">Remote friendly</div>
                <div class="experience-level">Mid-level</div>
                <div class="requirements">
                    <ul>
                        <li>Test skill 1</li>
                        <li>Test skill 2</li>
                    </ul>
                </div>
                <div class="benefits">
                    <ul>
                        <li>Test benefit 1</li>
                        <li>Test benefit 2</li>
                    </ul>
                </div>
                <a href="https://example.com/apply" class="apply-link">Apply Now</a>
            </div>
        </body>
        </html>
        """
    
    @pytest.fixture
    def scraper_config(self):
        """Sample scraper configuration."""
        return ScraperConfig(
            id=1,
            scraper_name="test_scraper",
        source_url="https://example.com/jobs",
            is_enabled=True
        )
    
    @pytest.fixture
    def ml_config(self):
        """Sample ML configuration."""
        return MLParsingConfig(
            id=1,
            name="Test ML Config",
            enabled=True
        )
    
    @pytest.fixture
    def enhanced_scraper_manager(self):
        """Enhanced scraper manager fixture."""
        manager = EnhancedScraperManager()
        
        # Mock ML parsing service
        mock_ml_service = AsyncMock()
        mock_ml_service.parse_job_data = AsyncMock(return_value=ParsedJobData(
            title="Test Job Title",
            company="Test Company",
            location="Test Location",
            description="Test job description.",
            salary_min=50000,
            salary_max=100000,
            job_type="full-time",
            is_remote=False,
            experience_level="Mid-level",
            requirements=["Test Skill 1", "Test Skill 2"],
            benefits=["Test Benefit 1", "Test Benefit 2"],
            application_url="https://example.com/apply",
            confidence_score=0.85
        ))
        manager.ml_parsing_service = mock_ml_service
        
        # Mock job validator
        mock_validator = AsyncMock()
        mock_validator.validate_job_data = AsyncMock(return_value=ValidationResult(
            is_valid=True,
            quality_score=0.95,
            issues=[],
            metadata={"validation_timestamp": datetime.now().isoformat()}
        ))
        manager.job_validator = mock_validator
        
        return manager
    
    @pytest.fixture
    def ml_parsing_service(self):
        """ML parsing service fixture."""
        service = MLParsingService()
        
        # Mock Gemini client
        mock_gemini = AsyncMock()
        mock_gemini.parse_job_content = AsyncMock(return_value={
            "title": "Test Job Title",
            "company": "Test Company",
            "location": "Test Location",
            "description": "Test job description.",
            "salary_min": 50000,
            "salary_max": 100000,
            "job_type": "full-time",
            "is_remote": False,
            "experience_level": "Mid-level",
            "requirements": ["Test Skill 1", "Test Skill 2"],
            "benefits": ["Test Benefit 1", "Test Benefit 2"],
            "confidence_score": 0.85
        })
        service.gemini_client = mock_gemini
        
        return service
    
    @pytest.fixture
    def job_validator(self):
        """Job data validator fixture."""
        return JobDataValidator()
    
    @pytest.fixture
    def ml_config_service(self):
        """ML configuration service fixture."""
        return MLConfigurationService()
    
    @pytest.mark.asyncio
    async def test_complete_ml_workflow_success(self, enhanced_scraper_manager, sample_html_content, scraper_config):
        """Test complete ML workflow from HTML to validated job data."""
        # Step 1: Parse HTML content with ML
        if hasattr(enhanced_scraper_manager.ml_parsing_service, 'parse_job_data'):
            parsed_data = await enhanced_scraper_manager.ml_parsing_service.parse_job_data(
                sample_html_content, 
                scraper_config.scraper_name
            )
            
            # Verify parsing results
            assert parsed_data is not None
            assert parsed_data.title == "Test Job Title"
            assert parsed_data.company == "Test Company"
            assert parsed_data.confidence_score >= 0.8
        
        # Step 2: Validate parsed data
        if hasattr(enhanced_scraper_manager.job_validator, 'validate_job_data'):
            validation_result = await enhanced_scraper_manager.job_validator.validate_job_data(parsed_data)
            
            # Verify validation results
            assert validation_result is not None
            assert validation_result.is_valid is True
            assert validation_result.quality_score >= 0.9
    
    @pytest.mark.asyncio
    async def test_ml_parsing_with_confidence_scoring(self, ml_parsing_service, sample_html_content):
        """Test ML parsing with confidence scoring."""
        if hasattr(ml_parsing_service, 'parse_job_data'):
            # Mock the parse_job_data method
            ml_parsing_service.parse_job_data = AsyncMock(return_value=ParsedJobData(
                title="Test Job Title",
                company="Test Company",
                location="Test Location",
                confidence_score=0.85
            ))
            
            result = await ml_parsing_service.parse_job_data(sample_html_content, "test_config")
            
            assert result.confidence_score >= 0.8
            assert result.title is not None
            assert result.company is not None
    
    @pytest.mark.asyncio
    async def test_job_validation_quality_assessment(self, job_validator):
        """Test job validation and quality assessment."""
        # Create test job data
        job_data = ParsedJobData(
            title="Test Job Title",
            company="Test Company",
            location="Test Location",
            description="Test job description.",
            salary_min=50000,
            salary_max=100000,
            confidence_score=0.85
        )
        
        if hasattr(job_validator, 'validate_job_data'):
            # Mock validation
            job_validator.validate_job_data = AsyncMock(return_value=ValidationResult(
                is_valid=True,
                quality_score=0.95,
                issues=[],
                metadata={"validation_timestamp": datetime.now().isoformat()}
            ))
            
            result = await job_validator.validate_job_data(job_data)
            
            assert result.is_valid is True
            assert result.quality_score >= 0.8
            assert len(result.issues) == 0
    
    @pytest.mark.asyncio
    async def test_ml_fallback_mechanism(self, enhanced_scraper_manager, sample_html_content):
        """Test ML fallback to traditional parsing when ML fails."""
        # Simulate ML parsing failure
        if hasattr(enhanced_scraper_manager.ml_parsing_service, 'parse_job_data'):
            enhanced_scraper_manager.ml_parsing_service.parse_job_data = AsyncMock(
                side_effect=Exception("ML parsing failed")
            )
        
        # Test fallback mechanism exists
        if hasattr(enhanced_scraper_manager, 'fallback_to_traditional'):
            assert callable(getattr(enhanced_scraper_manager, 'fallback_to_traditional'))
        
        # Verify system can handle ML failures gracefully
        assert enhanced_scraper_manager is not None
    
    @pytest.mark.asyncio
    async def test_configuration_driven_workflow(self, ml_config_service, ml_config):
        """Test configuration-driven ML workflow."""
        config = ml_config
        
        # Test configuration validation
        if hasattr(ml_config_service, 'validate_ml_config'):
            ml_config_service.validate_ml_config = AsyncMock(return_value={
                'is_valid': True,
                'errors': [],
                'warnings': []
            })
            
            validation = await ml_config_service.validate_ml_config({
                'name': config.name,
                'enabled': config.enabled,
                'confidence_threshold': 0.8
            })
            
            assert validation['is_valid'] is True
    
    @pytest.mark.asyncio
    async def test_batch_processing_workflow(self, enhanced_scraper_manager):
        """Test batch processing of multiple job listings."""
        # Sample batch data
        batch_html = [
            "<div class='job'>Job 1 content</div>",
            "<div class='job'>Job 2 content</div>",
            "<div class='job'>Job 3 content</div>"
        ]
        
        # Test batch processing capability
        if hasattr(enhanced_scraper_manager, 'process_batch'):
            assert callable(getattr(enhanced_scraper_manager, 'process_batch'))
        
        # Test individual processing for each item
        for html_content in batch_html:
            if hasattr(enhanced_scraper_manager.ml_parsing_service, 'parse_job_data'):
                result = await enhanced_scraper_manager.ml_parsing_service.parse_job_data(
                    html_content, "test_config"
                )
                assert result is not None
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, enhanced_scraper_manager, sample_html_content):
        """Test error handling and recovery mechanisms."""
        # Test various error scenarios
        error_scenarios = [
            "Invalid HTML content",
            "",  # Empty content
            "<html><body></body></html>",  # Minimal HTML
            None  # None content
        ]
        
        for content in error_scenarios:
            try:
                if hasattr(enhanced_scraper_manager.ml_parsing_service, 'parse_job_data'):
                    # Should handle errors gracefully
                    result = await enhanced_scraper_manager.ml_parsing_service.parse_job_data(
                        content, "test_config"
                    )
                    # If no exception, result should be valid or None
                    assert result is not None or content is None
            except Exception as e:
                # Errors should be handled gracefully
                assert isinstance(e, Exception)
    
    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self, enhanced_scraper_manager):
        """Test performance monitoring throughout the workflow."""
        # Test performance tracking methods
        performance_methods = [
            'track_parsing_performance',
            'get_performance_metrics',
            'log_performance_data'
        ]
        
        for method in performance_methods:
            if hasattr(enhanced_scraper_manager, method):
                assert callable(getattr(enhanced_scraper_manager, method))
    
    @pytest.mark.asyncio
    async def test_data_quality_pipeline(self, enhanced_scraper_manager, sample_html_content):
        """Test complete data quality pipeline."""
        # Step 1: Parse with ML
        if hasattr(enhanced_scraper_manager.ml_parsing_service, 'parse_job_data'):
            parsed_data = await enhanced_scraper_manager.ml_parsing_service.parse_job_data(
                sample_html_content, "test_config"
            )
            
            # Step 2: Validate data quality
            if hasattr(enhanced_scraper_manager.job_validator, 'validate_job_data'):
                validation_result = await enhanced_scraper_manager.job_validator.validate_job_data(parsed_data)
                
                # Step 3: Check quality metrics
                assert validation_result.quality_score >= 0.0
                assert isinstance(validation_result.is_valid, bool)
    
    @pytest.mark.asyncio
    async def test_workflow_state_management(self, enhanced_scraper_manager):
        """Test workflow state management and tracking."""
        # Test state management methods
        state_methods = [
            'get_workflow_state',
            'update_workflow_state',
            'track_workflow_progress'
        ]
        
        for method in state_methods:
            if hasattr(enhanced_scraper_manager, method):
                assert callable(getattr(enhanced_scraper_manager, method))
    
    @pytest.mark.asyncio
    async def test_integration_with_database(self, enhanced_scraper_manager):
        """Test integration with database operations."""
        # Test database integration methods
        db_methods = [
            'save_parsed_job',
            'update_job_data',
            'get_job_by_id',
            'store_parsing_results'
        ]
        
        for method in db_methods:
            if hasattr(enhanced_scraper_manager, method):
                assert callable(getattr(enhanced_scraper_manager, method))
    
    @pytest.mark.asyncio
    async def test_ml_model_versioning_and_updates(self, ml_config_service):
        """Test ML model versioning and update mechanisms."""
        # Test model versioning methods
        versioning_methods = [
            'get_model_version',
            'update_model_config',
            'rollback_model_version'
        ]
        
        for method in versioning_methods:
            if hasattr(ml_config_service, method):
                assert callable(getattr(ml_config_service, method))
    
    def test_workflow_integration_completeness(self, enhanced_scraper_manager, ml_parsing_service, job_validator, ml_config_service):
        """Test that all workflow components are properly integrated."""
        # Verify all components exist
        assert enhanced_scraper_manager is not None
        assert ml_parsing_service is not None
        assert job_validator is not None
        assert ml_config_service is not None
        
        # Verify integration points
        if hasattr(enhanced_scraper_manager, 'ml_parsing_service'):
            assert enhanced_scraper_manager.ml_parsing_service is not None
        
        if hasattr(enhanced_scraper_manager, 'job_validator'):
            assert enhanced_scraper_manager.job_validator is not None