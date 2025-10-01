import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from ml_parsing_service import MLParsingService
from gemini_client import GeminiClient

try:
    from backend.schemas.ml_schemas import MLConfig
    from backend.schemas.job_schemas import JobCreate
except ImportError:
    # Mock schemas for testing
    class MLConfig:
        def __init__(self, **kwargs):
            self.id = kwargs.get('id', 'test')
            self.scraper_config_id = kwargs.get('scraper_config_id', 'test')
            self.enabled = kwargs.get('enabled', True)
            self.confidence_threshold = kwargs.get('confidence_threshold', 0.7)
            self.field_mapping = kwargs.get('field_mapping', {})
            self.validation_rules = kwargs.get('validation_rules', {})
    
    class JobCreate:
        pass


@pytest.fixture
def mock_gemini_client():
    """Mock Gemini client for testing."""
    client = Mock(spec=GeminiClient)
    client.parse_job_data = AsyncMock()
    return client


@pytest.fixture
def ml_config():
    """Sample ML configuration for testing."""
    return MLConfig(
        id="test-config",
        scraper_config_id="test-scraper",
        enabled=True,
        confidence_threshold=0.7,
        field_mapping={
            "title": "job_title",
            "company": "company_name",
            "location": "job_location"
        },
        validation_rules={
            "required_fields": ["title", "company"],
            "min_confidence": 0.6
        }
    )


@pytest.fixture
def ml_parsing_service():
    """ML parsing service with mocked dependencies."""
    service = MLParsingService()
    # Mock the Gemini model to avoid actual API calls
    service.model = Mock()
    service.model.generate_content = Mock()
    service.available = True
    return service


@pytest.mark.asyncio
class TestMLParsingService:
    """Test cases for ML parsing service."""

    async def test_parse_job_data_success(self, ml_parsing_service):
        """Test successful job data parsing."""
        # Mock HTML content
        html_content = "<div><h1>Test Engineer</h1><p>Test Company</p><span>Test Location</span></div>"
        
        # Mock Gemini response
        mock_response = Mock()
        mock_response.text = '''{
            "title": "Test Engineer",
            "company": "Test Company",
            "location": "Test Location",
            "confidence_indicators": {
                "title_confidence": 0.9,
                "company_confidence": 0.8,
                "overall_structure": 0.85
            }
        }'''
        ml_parsing_service.model.generate_content.return_value = mock_response
        
        # Mock database session and MLParsingConfig
        with patch('ml_parsing_service.get_db_session') as mock_db, \
             patch('ml_parsing_service.MLParsingConfig') as mock_ml_config_class:
            mock_session = Mock()
            mock_db.return_value = iter([mock_session])
            mock_ml_config = Mock()
            mock_ml_config.gemini_api_enabled = True
            mock_ml_config.field_mapping = '{}'
            mock_session.query.return_value.filter.return_value.first.return_value = mock_ml_config
            
            # Test parsing
            result = await ml_parsing_service.parse_job_data(html_content, "test-scraper")
            
            # Assertions
            assert result is not None
            assert result.title == "Test Engineer"
            assert result.company == "Test Company"
            assert result.confidence_score > 0.7

    async def test_parse_job_data_low_confidence(self, ml_parsing_service):
        """Test parsing with low confidence score."""
        html_content = "<div>Test unclear job posting</div>"
        
        # Mock low confidence response
        mock_response = Mock()
        mock_response.text = '''{
            "title": "Test Position",
            "company": "Test Company",
            "confidence_indicators": {
                "title_confidence": 0.2,
                "company_confidence": 0.3,
                "overall_structure": 0.25
            }
        }'''
        ml_parsing_service.model.generate_content.return_value = mock_response
        
        # Mock database session and MLParsingConfig
        with patch('ml_parsing_service.get_db_session') as mock_db, \
             patch('ml_parsing_service.MLParsingConfig') as mock_ml_config_class:
            mock_session = Mock()
            mock_db.return_value = iter([mock_session])
            mock_ml_config = Mock()
            mock_ml_config.gemini_api_enabled = True
            mock_ml_config.field_mapping = '{}'
            mock_session.query.return_value.filter.return_value.first.return_value = mock_ml_config
            
            # Test parsing
            result = await ml_parsing_service.parse_job_data(html_content, "test-scraper", confidence_threshold=0.7)
            
            # Should use fallback parsing due to low confidence
            assert result is not None
            assert result.confidence_score < 0.7

    async def test_parse_job_data_api_error(self, ml_parsing_service):
        """Test handling of API errors."""
        html_content = "<div>Test content</div>"
        
        # Mock API error
        ml_parsing_service.model.generate_content.side_effect = Exception("API Error")
        
        # Mock database session and MLParsingConfig
        with patch('ml_parsing_service.get_db_session') as mock_db, \
             patch('ml_parsing_service.MLParsingConfig') as mock_ml_config_class:
            mock_session = Mock()
            mock_db.return_value = iter([mock_session])
            mock_ml_config = Mock()
            mock_ml_config.gemini_api_enabled = True
            mock_ml_config.field_mapping = '{}'
            mock_session.query.return_value.filter.return_value.first.return_value = mock_ml_config
            
            # Test parsing
            result = await ml_parsing_service.parse_job_data(html_content, "test-scraper")
            
            # Should fallback to regex parsing on error
            assert result is not None
            assert result.confidence_score == 0.6  # Fallback confidence

    async def test_validate_job_data_success(self, ml_parsing_service):
        """Test successful data validation."""
        from ml_parsing_service import ParsedJobData
        
        parsed_data = ParsedJobData(
            title="Test Engineer",
            company="Test Company",
            location="Test Location",
            confidence_score=0.85
        )
        
        # Test validation
        result = await ml_parsing_service.validate_job_data(parsed_data)
        
        # Should be valid
        assert result['is_valid'] is True
        assert result['quality_score'] >= 0.5
        assert len(result['errors']) == 0

    async def test_validate_job_data_missing_required_fields(self, ml_parsing_service):
        """Test validation with missing required fields."""
        from ml_parsing_service import ParsedJobData
        
        parsed_data = ParsedJobData(
            title=None,  # Missing required title
            company="Test Company",
            location="Test Location",
            confidence_score=0.85
        )
        
        # Test validation
        result = await ml_parsing_service.validate_job_data(parsed_data)
        
        # Should be invalid
        assert result['is_valid'] is False
        assert len(result['errors']) > 0
        assert 'Job title is required' in result['errors']

    async def test_validate_job_data_low_confidence(self, ml_parsing_service):
        """Test validation with low confidence."""
        from ml_parsing_service import ParsedJobData
        
        parsed_data = ParsedJobData(
            title="Test Engineer",
            company="Test Company",
            location="Test Location",
            confidence_score=0.3  # Low confidence
        )
        
        # Test validation
        result = await ml_parsing_service.validate_job_data(parsed_data)
        
        # Should have warnings about low confidence
        assert 'Low parsing confidence score' in result['warnings']
        assert result['quality_score'] > 0  # Still has some quality due to complete data

    async def test_fallback_parsing(self, ml_parsing_service):
        """Test fallback parsing when ML is not available."""
        # Disable ML availability
        ml_parsing_service.available = False
        
        html_content = "<h1>Test Engineer</h1><span>Test Company</span><div>Test Location</div>"
        
        # Mock database session and MLParsingConfig
        with patch('ml_parsing_service.get_db_session') as mock_db, \
             patch('ml_parsing_service.MLParsingConfig') as mock_ml_config_class:
            mock_session = Mock()
            mock_db.return_value = iter([mock_session])
            mock_ml_config = Mock()
            mock_ml_config.gemini_api_enabled = True
            mock_ml_config.field_mapping = '{}'
            mock_session.query.return_value.filter.return_value.first.return_value = mock_ml_config
            
            # Test parsing
            result = await ml_parsing_service.parse_job_data(html_content, "test-scraper")
            
            # Should use fallback parsing
            assert result is not None
            assert result.confidence_score == 0.6  # Fallback confidence
            assert result.parsing_metadata['parsing_method'] == 'fallback_regex'