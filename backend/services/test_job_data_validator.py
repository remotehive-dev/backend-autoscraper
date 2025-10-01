import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from backend.services.job_validation_service import JobDataValidator, ValidationResult, ValidationIssue, ValidationSeverity
from backend.services.ml_parsing_service import ParsedJobData
from datetime import datetime


@pytest.fixture
def job_validator():
    """Job data validator instance for testing."""
    return JobDataValidator()


@pytest.fixture
def valid_parsed_job_data():
    """Valid parsed job data for testing."""
    return ParsedJobData(
        title="Test Software Engineer",
        company="Test Company",
        location="Test Location",
        description="Test job description with sufficient content for validation and testing purposes.",
        salary_min=50000,
        salary_max=100000,
        job_type="full-time",
        is_remote=False,
        experience_level="Mid-level",
        requirements=["Test Skill 1", "Test Skill 2"],
        posted_date=datetime.now(),
        application_url="https://example.com/jobs/test-engineer",
        confidence_score=0.85
    )


@pytest.fixture
def invalid_parsed_job_data():
    """Invalid parsed job data for testing."""
    return ParsedJobData(
        title="",  # Empty title
        company="X" * 300,  # Too long company name
        location="Invalid Location 123!@#",  # Invalid characters
        description="Short",  # Too short description
        salary_min=-1000,  # Invalid salary
        salary_max=10000000,  # Unrealistic salary
        job_type="Invalid Type",  # Invalid job type
        is_remote=None,
        experience_level="Unknown",  # Invalid experience level
        requirements=[],
        posted_date=None,
        application_url="not-a-url",  # Invalid URL
        confidence_score=0.2
    )


@pytest.mark.asyncio
class TestJobDataValidator:
    """Test cases for job data validator."""

    async def test_validate_job_data_valid(self, job_validator, valid_parsed_job_data):
        """Test validation of valid job data."""
        result = await job_validator.validate_job_data(valid_parsed_job_data)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.quality_score > 0.6
        assert result.completeness_score > 0.0
        assert result.accuracy_score > 0.0

    async def test_validate_job_data_invalid(self, job_validator, invalid_parsed_job_data):
        """Test validation of invalid job data."""
        result = await job_validator.validate_job_data(invalid_parsed_job_data)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is False
        assert result.quality_score < 0.6
        assert len(result.issues) > 0
        assert any(issue.severity == ValidationSeverity.CRITICAL for issue in result.issues)

    async def test_validation_result_structure(self, job_validator, valid_parsed_job_data):
        """Test that validation result has expected structure."""
        result = await job_validator.validate_job_data(valid_parsed_job_data)
        
        # Check ValidationResult attributes
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'quality_score')
        assert hasattr(result, 'completeness_score')
        assert hasattr(result, 'accuracy_score')
        assert hasattr(result, 'issues')
        assert hasattr(result, 'field_scores')
        assert hasattr(result, 'recommendations')
        assert hasattr(result, 'metadata')
        
        # Check types
        assert isinstance(result.is_valid, bool)
        assert isinstance(result.quality_score, float)
        assert isinstance(result.completeness_score, float)
        assert isinstance(result.accuracy_score, float)
        assert isinstance(result.issues, list)
        assert isinstance(result.field_scores, dict)
        assert isinstance(result.recommendations, list)
        assert isinstance(result.metadata, dict)

    async def test_validation_with_config_id(self, job_validator, valid_parsed_job_data):
        """Test validation with config_id parameter."""
        config_id = "test-config-123"
        
        with patch.object(job_validator, '_store_validation_metrics', new_callable=AsyncMock) as mock_store:
            result = await job_validator.validate_job_data(valid_parsed_job_data, config_id=config_id)
            
            assert result.metadata['config_id'] == config_id
            mock_store.assert_called_once()

    async def test_validation_batch_method_exists(self, job_validator):
        """Test that validate_job_batch method exists."""
        assert hasattr(job_validator, 'validate_job_batch')
        assert callable(getattr(job_validator, 'validate_job_batch'))

    async def test_validation_statistics_method_exists(self, job_validator):
        """Test that get_validation_statistics method exists."""
        assert hasattr(job_validator, 'get_validation_statistics')
        assert callable(getattr(job_validator, 'get_validation_statistics'))

    async def test_field_validation_scoring(self, job_validator, valid_parsed_job_data):
        """Test that field scores are calculated correctly."""
        result = await job_validator.validate_job_data(valid_parsed_job_data)
        
        # Should have field scores for validated fields
        assert len(result.field_scores) > 0
        
        # All scores should be between 0 and 1
        for field_name, score in result.field_scores.items():
            assert 0.0 <= score <= 1.0, f"Score for {field_name} is out of range: {score}"

    async def test_critical_issues_make_invalid(self, job_validator):
        """Test that critical validation issues make job invalid."""
        # Create job data with missing required field
        invalid_data = ParsedJobData(
            title="",  # Missing required title
            company="Test Company",
            location="Test Location",
            description="Test description with enough content to pass length requirements.",
            confidence_score=0.9
        )
        
        result = await job_validator.validate_job_data(invalid_data)
        
        assert result.is_valid is False
        assert any(issue.severity == ValidationSeverity.CRITICAL for issue in result.issues)

    async def test_validation_metadata_contains_timestamps(self, job_validator, valid_parsed_job_data):
        """Test that validation metadata contains required information."""
        result = await job_validator.validate_job_data(valid_parsed_job_data)
        
        assert 'validation_timestamp' in result.metadata
        assert 'total_issues' in result.metadata
        assert 'critical_issues' in result.metadata
        assert 'warning_issues' in result.metadata
        
        # Check that timestamp is a valid ISO format
        timestamp = result.metadata['validation_timestamp']
        assert isinstance(timestamp, str)
        # Should be able to parse the timestamp
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))